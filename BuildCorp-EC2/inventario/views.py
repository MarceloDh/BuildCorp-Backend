import uuid
from datetime import timedelta
from urllib.parse import urlencode

from django import forms
from django.contrib import messages
from django.core import signing
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, redirect_to_login
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Exists, OuterRef, ProtectedError, Q
from django.forms import modelform_factory
from django.db import IntegrityError, transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from . import services
from .access import exigir_acceso, perfil_contratista, puede_operar
from .forms import DevolucionForm, EntregaForm, PagoSimuladoForm, ProgramacionForm, RegistroContratistaForm, TrasladoForm
from .models import Activo, Bodega, Contratista, Mantenimiento, Obra, Prestamo, Servicio, SolicitudServicio
from .servicios_demo import CATEGORIAS_SERVICIOS, normalizar, pesos
from .validaciones import rut_normalizado


CATALOGOS = {
    "obras": (Obra, "Obras", ("nombre", "direccion")),
    "bodegas": (Bodega, "Bodegas", ("obra", "nombre")),
    "contratistas": (Contratista, "Contratistas", (
        "nombre", "identificador", "contacto", "telefono", "direccion", "comuna", "region",
        "bloqueado_manual", "motivo_bloqueo",
    )),
    "servicios": (Servicio, "Servicios del catálogo", ("codigo", "nombre", "categoria", "descripcion", "unidad", "tarifa", "publicado")),
}


def pagina(request, registros):
    return Paginator(registros, 25).get_page(request.GET.get("pagina"))


class AccesoBuildCorp(LoginView):
    def get_default_redirect_url(self):
        if puede_operar(self.request.user):
            return reverse("inicio")
        if perfil_contratista(self.request.user) is not None:
            return reverse("portal_contratista")
        return reverse("portada")


def portada(request):
    return render(request, "inventario/portada.html", {"servicios": Servicio.objects.filter(publicado=True)[:3]})


@never_cache
def registro(request):
    form = RegistroContratistaForm(request.POST if request.method == "POST" else None)
    siguiente = request.POST.get("next", request.GET.get("next", ""))
    if not url_has_allowed_host_and_scheme(siguiente, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        siguiente = ""
    if request.method == "POST" and form.is_valid():
        try:
            usuario = form.save()
        except IntegrityError:
            form.add_error(None, "La cuenta o el identificador ya existe. Revisa tus datos.")
        else:
            login(request, usuario)
            return redirect(siguiente or "portal_contratista")
    return render(request, "registration/registro.html", {"form": form, "siguiente": siguiente})


@require_safe
def sugerencias_busqueda(request):
    consulta = request.GET.get("q", "").strip()[:120]
    if len(consulta) < 2:
        return JsonResponse({"resultados": []})
    termino = normalizar(consulta)
    resultados = [
        {"nombre": servicio.nombre, "categoria": servicio.categoria,
         "url": reverse("pago_simulado", args=[servicio.codigo])}
        for servicio in Servicio.objects.filter(publicado=True)
        if termino in normalizar(f"{servicio.nombre} {servicio.categoria} {servicio.descripcion}")
    ][:6]
    nombres = Activo.objects.filter(
        mostrar_en_catalogo=True, dado_de_baja=False, nombre__icontains=consulta,
    ).order_by("nombre").values_list("nombre", flat=True).distinct()[:3]
    resultados.extend(
        {"nombre": nombre, "categoria": "Equipo publicado",
         "url": reverse("catalogo_publico") + "?" + urlencode({"q": nombre})}
        for nombre in nombres if nombre not in {item["nombre"] for item in resultados}
    )
    return JsonResponse({"resultados": resultados[:8]})


@require_safe
def catalogo_publico(request):
    consulta = request.GET.get("q", "").strip()[:120]
    nombres = Activo.objects.filter(mostrar_en_catalogo=True, dado_de_baja=False)
    if consulta:
        nombres = nombres.filter(nombre__icontains=consulta)
    nombres = nombres.order_by("nombre").values_list("nombre", flat=True).distinct()
    termino = normalizar(consulta)
    categoria = request.GET.get("categoria", "")
    if categoria not in {item["codigo"] for item in CATEGORIAS_SERVICIOS}:
        categoria = ""
    servicios = [
        servicio for servicio in Servicio.objects.filter(publicado=True)
        if (not categoria or servicio.grupo == categoria)
        and termino in normalizar(f"{servicio.nombre} {servicio.categoria} {servicio.descripcion}")
    ]
    return render(request, "inventario/catalogo_publico.html", {
        "pagina": pagina(request, nombres), "q": consulta, "servicios": servicios,
        "categorias": CATEGORIAS_SERVICIOS, "categoria": categoria,
    })


@never_cache
@require_http_methods(["GET", "HEAD", "POST"])
def pago_simulado(request, codigo):
    servicio = get_object_or_404(Servicio, codigo=codigo, publicado=True)
    contratista = perfil_contratista(request.user)
    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect_to_login(request.path)
        if contratista is None:
            raise PermissionDenied
    inicial = {
        "nombre": request.user.first_name if request.user.is_authenticated else "",
        "apellido": request.user.last_name if request.user.is_authenticated else "",
        "correo": (contratista.contacto or request.user.email) if contratista else "",
        "token": signing.dumps(
            {"cuenta": request.user.pk, "servicio": codigo, "tarifa": servicio.tarifa, "clave": str(uuid.uuid4())},
            salt="solicitud-servicio",
        ),
    }
    if contratista:
        inicial.update({campo: getattr(contratista, campo) for campo in ("telefono", "direccion", "comuna", "region")})
        try:
            inicial["rut"] = rut_normalizado(contratista.identificador)
        except ValidationError:
            inicial["rut"] = ""
    form = PagoSimuladoForm(request.POST if request.method == "POST" else None, initial=inicial)
    plural = {"día": "días", "viaje": "viajes", "visita": "visitas"}[servicio.unidad]
    form.fields["cantidad"].label = f"Cantidad ({plural})"
    form.fields["fecha"].widget.attrs["min"] = timezone.localdate().isoformat()
    total_visible = servicio.tarifa_visible
    if request.method == "POST":
        total_visible = "—"
        if form.is_valid():
            try:
                token = signing.loads(form.cleaned_data["token"], salt="solicitud-servicio", max_age=7200)
                if token["cuenta"] != request.user.pk or token["servicio"] != codigo:
                    raise signing.BadSignature
                if token["tarifa"] != servicio.tarifa:
                    raise ValidationError("La tarifa cambió. Abre el servicio de nuevo para revisar el importe.")
                solicitud = services.registrar_solicitud(
                    contratista=contratista, servicio=servicio, referencia=uuid.UUID(token["clave"]),
                    datos=form.cleaned_data,
                )
            except (signing.BadSignature, ValueError, KeyError):
                form.add_error(None, "La página venció. Abre el servicio de nuevo antes de confirmar.")
            except ValidationError as error:
                for mensaje in error.messages:
                    form.add_error(None, mensaje)
            else:
                return redirect("solicitud_detalle", referencia=solicitud.referencia)
    return render(request, "inventario/pago_simulado.html", {
        "servicio": servicio, "form": form, "total_visible": total_visible,
        "contratista": contratista,
        "bloqueado": contratista and (contratista.bloqueado_manual or contratista.prestamos.vencidos().exists()),
    })


def obtener_solicitud(request, referencia):
    registros = SolicitudServicio.objects.select_related("contratista", "activo", "prestamo")
    if not puede_operar(request.user):
        contratista = perfil_contratista(request.user)
        if contratista is None:
            raise PermissionDenied
        registros = registros.filter(contratista=contratista)
    return get_object_or_404(registros, referencia=referencia)


@login_required
@never_cache
def solicitud_detalle(request, referencia):
    solicitud = obtener_solicitud(request, referencia)
    return render(request, "inventario/solicitud.html", {
        "solicitud": solicitud, "total_visible": pesos(solicitud.total),
        "neto_visible": pesos(solicitud.neto), "iva_visible": pesos(solicitud.iva),
    })


@login_required
@never_cache
@require_safe
def solicitud_pdf(request, referencia, documento):
    from .documentos_pago import generar_documento

    solicitud = obtener_solicitud(request, referencia)
    if documento not in ("informe", "factura"):
        raise Http404
    if documento == "factura" and (solicitud.tipo_documento != "factura" or not solicitud.pago_aprobado):
        raise Http404
    from django.http import HttpResponse
    response = HttpResponse(generar_documento(solicitud, documento), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{documento}-{solicitud.numero_documento}.pdf"'
    return response


@login_required
@require_POST
def solicitud_cancelar(request, referencia):
    registros = SolicitudServicio.objects.all()
    if not puede_operar(request.user):
        registros = registros.filter(contratista__cuenta=request.user)
    solicitud = get_object_or_404(registros, referencia=referencia)
    try:
        services.cancelar_solicitud(solicitud)
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        messages.success(request, "Solicitud cancelada. La unidad vuelve al inventario disponible.")
    return redirect("solicitud_detalle", referencia=referencia)


@login_required
def solicitudes_bodega(request):
    exigir_acceso(request.user)
    return render(request, "inventario/solicitudes.html", {
        "pagina": pagina(request, SolicitudServicio.objects.select_related("contratista", "prestamo")),
    })


def prestamos_de_contratista(user):
    contratista = perfil_contratista(user)
    if contratista is None:
        raise PermissionDenied
    return contratista, contratista.prestamos.select_related("activo", "bodega__obra")


@login_required
@never_cache
@require_safe
def portal_contratista(request):
    contratista, prestamos_propios = prestamos_de_contratista(request.user)
    ahora = timezone.now()
    estados = {
        "vigentes": Q(devuelto_en__isnull=True, vence_en__gte=ahora),
        "vencidos": Q(devuelto_en__isnull=True, vence_en__lt=ahora),
        "devueltos": Q(devuelto_en__isnull=False),
    }
    totales = prestamos_propios.aggregate(
        todos=Count("pk"), **{nombre: Count("pk", filter=filtro) for nombre, filtro in estados.items()},
    )
    estado = request.GET.get("estado", "")
    if estado in estados:
        prestamos_propios = prestamos_propios.filter(estados[estado])
    else:
        estado = ""
    return render(request, "inventario/portal_contratista.html", {
        "contratista": contratista,
        "vencidos": totales["vencidos"],
        "totales": totales,
        "estado": estado,
        "solicitudes": contratista.solicitudes.select_related("prestamo")[:8],
        "pagina": pagina(request, prestamos_propios),
    })


@login_required
@never_cache
@require_safe
def prestamo_contratista(request, pk):
    _, prestamos_propios = prestamos_de_contratista(request.user)
    prestamo = get_object_or_404(prestamos_propios, pk=pk)
    return render(request, "inventario/prestamo_contratista.html", {"prestamo": prestamo})


@login_required
def inicio(request):
    exigir_acceso(request.user)
    vencidos = Prestamo.objects.vencidos().select_related("activo", "contratista", "bodega")
    exigibles = Mantenimiento.objects.exigibles().select_related("activo")
    return render(request, "inventario/inicio.html", {
        "activos": Activo.objects.count(),
        "abiertos": Prestamo.objects.abiertos().count(),
        "vencidos_total": vencidos.count(),
        "vencidos": vencidos[:8],
        "exigibles_total": exigibles.count(),
        "exigibles": exigibles[:8],
    })


@login_required
def activos(request):
    exigir_acceso(request.user)
    registros = Activo.objects.select_related("bodega__obra")
    consulta = request.GET.get("q", "").strip()
    if consulta:
        registros = registros.filter(Q(codigo__icontains=consulta) | Q(nombre__icontains=consulta))
    return render(request, "inventario/activos.html", {"pagina": pagina(request, registros), "q": consulta})


@login_required
def activo_detalle(request, pk):
    exigir_acceso(request.user)
    activo = get_object_or_404(Activo.objects.select_related("bodega__obra"), pk=pk)
    return render(request, "inventario/activo.html", {
        "activo": activo,
        "prestamos": activo.prestamos.select_related("contratista")[:20],
        "mantenimientos": activo.mantenimientos.all(),
        "traslados": activo.traslados.select_related("origen__obra", "destino__obra", "registrado_por")[:20],
    })


def formulario(request, form, titulo, volver, **contexto):
    return render(request, "inventario/formulario.html", {
        "form": form, "titulo": titulo, "volver": volver, **contexto,
    })


@login_required
@transaction.atomic
def activo_editar(request, pk=None):
    exigir_acceso(request.user, supervision=True)
    registros = Activo.objects.select_for_update() if request.method == "POST" else Activo.objects.all()
    instancia = get_object_or_404(registros, pk=pk) if pk is not None else None
    campos = ["codigo", "nombre", "descripcion", "mostrar_en_catalogo", "servicio"]
    if instancia is None:
        campos += ["bodega", "horas_uso"]
    clase = modelform_factory(Activo, fields=campos, widgets={"descripcion": forms.Textarea(attrs={"rows": 3})})
    form = clase(request.POST if request.method == "POST" else None, instance=instancia)
    if instancia and instancia.estado != Activo.Estado.DISPONIBLE:
        form.fields["servicio"].disabled = True
    if request.method == "POST" and form.is_valid():
        activo = form.save(commit=False)
        activo.save(update_fields=campos if instancia else None)
        messages.success(request, "Herramienta guardada.")
        return redirect("activo_detalle", pk=activo.pk)
    volver = reverse("activo_detalle", args=[pk]) if instancia else reverse("activos")
    return formulario(request, form, "Editar herramienta" if instancia else "Nueva herramienta", volver)


@login_required
def catalogo(request, tipo):
    exigir_acceso(request.user)
    if tipo not in CATALOGOS:
        raise Http404
    modelo, titulo, _ = CATALOGOS[tipo]
    registros = modelo.objects.all()
    if tipo == "bodegas":
        registros = registros.select_related("obra")
    if tipo == "contratistas":
        registros = registros.annotate(
            bloqueado=Exists(Prestamo.objects.vencidos().filter(contratista_id=OuterRef("pk"))),
        )
    return render(request, "inventario/catalogo.html", {
        "tipo": tipo, "titulo": titulo, "pagina": pagina(request, registros),
    })


@login_required
def catalogo_editar(request, tipo, pk=None):
    exigir_acceso(request.user, supervision=True)
    if tipo not in CATALOGOS:
        raise Http404
    modelo, _, campos = CATALOGOS[tipo]
    instancia = get_object_or_404(modelo, pk=pk) if pk is not None else None
    clase = modelform_factory(modelo, fields=campos)
    form = clase(request.POST if request.method == "POST" else None, instance=instancia)
    if instancia and modelo is Bodega:
        form.fields["obra"].disabled = True
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Registro guardado.")
        return redirect("catalogo", tipo=tipo)
    nombre = str(modelo._meta.verbose_name)
    return formulario(request, form, f"{'Editar' if instancia else 'Registrar'} {nombre}", reverse("catalogo", args=[tipo]))


@login_required
@require_POST
def eliminar(request, tipo, pk):
    exigir_acceso(request.user, supervision=True)
    if tipo == "activos":
        modelo = Activo
        volver = reverse("activos")
    elif tipo in CATALOGOS:
        modelo = CATALOGOS[tipo][0]
        volver = reverse("catalogo", args=[tipo])
    else:
        raise Http404
    objeto = get_object_or_404(modelo, pk=pk)
    try:
        objeto.delete()
    except ProtectedError:
        messages.error(request, "El registro está asociado a otros datos y debe conservarse.")
    else:
        messages.success(request, "Registro eliminado.")
    return redirect(volver)


@login_required
def prestamos(request):
    exigir_acceso(request.user)
    registros = Prestamo.objects.select_related("activo", "contratista", "bodega__obra")
    filtro = request.GET.get("estado")
    if filtro == "vencidos":
        registros = registros.vencidos()
    elif filtro == "abiertos":
        registros = registros.abiertos()
    return render(request, "inventario/prestamos.html", {"pagina": pagina(request, registros), "filtro": filtro})


@login_required
def prestamo_detalle(request, pk):
    exigir_acceso(request.user)
    prestamo = get_object_or_404(
        Prestamo.objects.select_related("activo", "contratista", "bodega__obra", "entrega_por", "devolucion_por"),
        pk=pk,
    )
    return render(request, "inventario/prestamo.html", {"prestamo": prestamo})


@login_required
def entrega(request):
    exigir_acceso(request.user)
    inicial = {"activo": request.GET.get("activo")}
    if request.GET.get("solicitud"):
        try:
            referencia = uuid.UUID(request.GET["solicitud"])
        except ValueError:
            raise Http404 from None
        reserva = get_object_or_404(SolicitudServicio, referencia=referencia, estado="pendiente", pago_aprobado=True)
        if reserva.activo_id is None:
            raise Http404
        inicial.update(
            solicitud=reserva, activo=reserva.activo, contratista=reserva.contratista,
            vence_en=timezone.now() + timedelta(days=reserva.cantidad),
        )
    form = EntregaForm(
        request.POST if request.method == "POST" else None,
        initial=inicial,
    )
    if request.method == "POST" and form.is_valid():
        try:
            prestamo = services.entregar(**form.cleaned_data, usuario=request.user)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Entrega registrada.")
            return redirect("prestamo_detalle", pk=prestamo.pk)
    return formulario(request, form, "Registrar entrega", reverse("prestamos"))


@login_required
def devolucion(request, pk):
    exigir_acceso(request.user)
    prestamo = get_object_or_404(Prestamo, pk=pk)
    if prestamo.devuelto_en:
        return redirect("prestamo_detalle", pk=pk)
    form = DevolucionForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            services.devolver(prestamo=prestamo, **form.cleaned_data, usuario=request.user)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Devolución registrada.")
            return redirect("prestamo_detalle", pk=pk)
    return formulario(request, form, "Registrar devolución", reverse("prestamo_detalle", args=[pk]), detalle=str(prestamo))


@login_required
def traslado(request, pk):
    exigir_acceso(request.user, supervision=True)
    activo = get_object_or_404(Activo, pk=pk)
    form = TrasladoForm(request.POST if request.method == "POST" else None)
    form.fields["destino"].queryset = Bodega.objects.exclude(pk=activo.bodega_id)
    if request.method == "POST" and form.is_valid():
        try:
            services.trasladar(activo=activo, **form.cleaned_data, usuario=request.user)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Traslado registrado.")
            return redirect("activo_detalle", pk=pk)
    return formulario(request, form, "Trasladar herramienta", reverse("activo_detalle", args=[pk]), detalle=str(activo))


@login_required
@require_POST
def cambiar_baja(request, pk):
    exigir_acceso(request.user, supervision=True)
    activo = get_object_or_404(Activo, pk=pk)
    accion = request.POST.get("accion")
    if accion not in {"baja", "reactivar"}:
        raise Http404
    try:
        services.cambiar_baja(activo, dar_de_baja=accion == "baja")
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        messages.success(request, "Estado de la herramienta actualizado.")
    return redirect("activo_detalle", pk=pk)


@login_required
def mantenimientos(request):
    exigir_acceso(request.user)
    registros = Mantenimiento.objects.select_related("activo")
    exigibles = request.GET.get("estado") == "exigibles"
    if exigibles:
        registros = registros.exigibles()
    return render(request, "inventario/mantenimientos.html", {
        "pagina": pagina(request, registros), "exigibles": exigibles,
    })


@login_required
def programar(request, pk, mantenimiento_id=None):
    exigir_acceso(request.user, supervision=True)
    activo = get_object_or_404(Activo, pk=pk)
    registro = None
    inicial = {}
    if mantenimiento_id is not None:
        registro = get_object_or_404(activo.mantenimientos.pendientes(), pk=mantenimiento_id)
        inicial = {
            "tarea": registro.tarea,
            "fecha_limite": registro.fecha_limite.isoformat() if registro.fecha_limite else None,
            "horas_limite": registro.horas_limite,
            "observaciones": registro.observaciones,
        }
    form = ProgramacionForm(request.POST if request.method == "POST" else None, initial=inicial)
    if request.method == "POST" and form.is_valid():
        try:
            services.programar(activo=activo, registro=registro, **form.cleaned_data)
        except ValidationError as error:
            for mensaje in error.messages:
                form.add_error(None, mensaje)
        else:
            messages.success(request, "Mantenimiento actualizado." if registro else "Mantenimiento programado.")
            return redirect("activo_detalle", pk=pk)
    titulo = "Editar mantenimiento" if registro else "Programar mantenimiento"
    return formulario(request, form, titulo, reverse("activo_detalle", args=[pk]), detalle=str(activo))


@login_required
@require_POST
def cambiar_mantenimiento(request, pk, accion):
    exigir_acceso(request.user, supervision=True)
    mantenimiento = get_object_or_404(Mantenimiento, pk=pk)
    try:
        services.cambiar_mantenimiento(mantenimiento, accion)
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        messages.success(request, "Mantenimiento actualizado.")
    return redirect("activo_detalle", pk=mantenimiento.activo_id)
