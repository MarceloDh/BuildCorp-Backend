import base64
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import connection, connections
from django.test import Client, RequestFactory, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image, ImageDraw

from . import services
from .access import OPERADOR
from .models import Activo, Bodega, Contratista, Mantenimiento, Obra, Prestamo, Servicio, SolicitudServicio, Traslado
from .validaciones import rut_normalizado

DATOS_PAGO = {
    "rut": "12345678-5", "metodo_pago": "webpay", "tipo_documento": "comprobante",
    "razon_social": "", "rut_facturacion": "", "giro": "", "direccion_facturacion": "",
}


def firma_prueba():
    imagen = Image.new("RGB", (640, 200), "white")
    ImageDraw.Draw(imagen).line([(20, 140), (55, 35), (130, 90)], fill="black", width=3)
    salida = BytesIO()
    imagen.save(salida, format="PNG")
    return "data:image/png;base64," + base64.b64encode(salida.getvalue()).decode()


class OperacionesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.supervisor = get_user_model().objects.create_superuser("supervisor", password="clave-de-prueba")
        cls.operador = get_user_model().objects.create_user("bodega", password="clave-de-prueba")
        cls.operador.groups.add(Group.objects.create(name=OPERADOR))
        cls.obra = Obra.objects.create(nombre="Obra Norte", direccion="Pasaje Uno 123")
        cls.bodega = Bodega.objects.create(obra=cls.obra, nombre="Central")
        cls.destino = Bodega.objects.create(obra=cls.obra, nombre="Secundaria")
        cls.contratista = Contratista.objects.create(nombre="Montajes Norte", identificador="DEMO-1")
        cls.activo = Activo.objects.create(codigo="T-01", nombre="Taladro", bodega=cls.bodega)
        cls.segundo = Activo.objects.create(codigo="T-02", nombre="Sierra", bodega=cls.bodega)

    def entregar(self, activo, firma=None):
        vence = timezone.localtime() + timedelta(days=1)
        return self.client.post(reverse("entrega"), {
            "activo": activo.pk, "contratista": self.contratista.pk,
            "vence_en": vence.strftime("%Y-%m-%dT%H:%M"), "responsable": "Patricia",
            "firma": firma_prueba() if firma is None else firma,
        })

    def test_entrega_atraso_devolucion_y_mantenimiento_por_horas(self):
        self.client.force_login(self.supervisor)
        response = self.client.post(reverse("programar", args=[self.activo.pk]), {
            "tarea": "Revisar motor", "horas_limite": 5,
        })
        self.assertRedirects(response, reverse("activo_detalle", args=[self.activo.pk]))
        orden = Mantenimiento.objects.get()

        self.client.force_login(self.operador)
        self.assertEqual(self.entregar(self.activo).status_code, 302)
        prestamo = Prestamo.objects.get()
        self.assertEqual(prestamo.activo.estado, Activo.Estado.EN_USO)
        self.assertContains(self.client.get(reverse("prestamo_detalle", args=[prestamo.pk])), "Firma de entrega")

        ahora = timezone.now()
        Prestamo.objects.filter(pk=prestamo.pk).update(
            entregado_en=ahora - timedelta(days=2), vence_en=ahora - timedelta(days=1),
        )
        self.assertContains(self.client.get(reverse("inicio")), "Montajes Norte")
        self.assertContains(self.entregar(self.segundo), "tiene devoluciones vencidas")
        self.assertEqual(Prestamo.objects.count(), 1)

        datos = {"horas": 5, "responsable": "Patricia", "firma": firma_prueba()}
        self.assertEqual(self.client.post(reverse("devolucion", args=[prestamo.pk]), datos).status_code, 302)
        self.assertEqual(self.client.post(reverse("devolucion", args=[prestamo.pk]), datos).status_code, 302)
        self.activo.refresh_from_db()
        self.assertEqual(self.activo.horas_uso, 5)
        self.assertContains(self.entregar(self.activo), "mantenimiento pendiente")
        self.assertEqual(self.entregar(self.segundo).status_code, 302)
        self.assertTrue(Mantenimiento.objects.exigibles().filter(pk=orden.pk).exists())

        self.client.force_login(self.supervisor)
        for accion, estado in (("iniciar", Activo.Estado.MANTENIMIENTO), ("completar", Activo.Estado.DISPONIBLE)):
            self.assertEqual(self.client.post(reverse("cambiar_mantenimiento", args=[orden.pk, accion])).status_code, 302)
            self.assertEqual(self.activo.estado, estado)
        self.assertEqual(self.entregar(self.activo).status_code, 302)

    def test_permisos_firma_y_traslado(self):
        self.assertEqual(self.client.get(reverse("inicio")).status_code, 302)
        self.assertEqual(self.client.get(reverse("activo-list")).status_code, 403)
        self.client.force_login(self.operador)
        self.assertEqual(self.client.get(reverse("activo_nuevo")).status_code, 403)
        self.assertContains(self.entregar(self.activo, ""), "Dibuja la firma")
        self.assertFalse(Prestamo.objects.exists())
        self.assertEqual(self.client.get(reverse("activo-list")).json()["count"], 2)

        self.client.force_login(self.supervisor)
        response = self.client.post(reverse("traslado", args=[self.activo.pk]), {"destino": self.destino.pk})
        self.assertRedirects(response, reverse("activo_detalle", args=[self.activo.pk]))
        self.activo.refresh_from_db()
        self.assertEqual(self.activo.bodega_id, self.destino.pk)
        self.assertEqual(Traslado.objects.get().origen_id, self.bodega.pk)
        self.client.post(reverse("eliminar", args=["activos", self.activo.pk]))
        self.assertTrue(Activo.objects.filter(pk=self.activo.pk).exists())

    def test_listados_y_panel_interno(self):
        self.assertContains(self.client.get(reverse("login")), "Ingreso a BuildCorp")
        self.client.force_login(self.supervisor)
        for nombre in ("activos", "prestamos", "mantenimientos", "admin:index"):
            response = self.client.get(reverse(nombre))
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, "Django")
        for tipo in ("obras", "bodegas", "contratistas"):
            self.assertEqual(self.client.get(reverse("catalogo", args=[tipo])).status_code, 200)
        listado = reverse("admin:inventario_activo_changelist")
        self.assertContains(self.client.get(listado, {"estado": "disponible"}), "T-01")
        self.assertNotContains(self.client.get(listado, {"estado": "en_uso"}), "T-01")

    def test_mantenimiento_por_fecha_y_baja_reintentada(self):
        self.client.force_login(self.supervisor)
        programar = reverse("programar", args=[self.activo.pk])
        self.assertEqual(self.client.post(programar, {
            "tarea": "Revisión por fecha", "fecha_limite": timezone.localdate().isoformat(),
        }).status_code, 302)
        orden = Mantenimiento.objects.get()
        self.assertContains(self.entregar(self.activo), "mantenimiento pendiente")
        editar = reverse("editar_mantenimiento", args=[self.activo.pk, orden.pk])
        self.assertEqual(self.client.post(editar, {
            "tarea": orden.tarea, "fecha_limite": (timezone.localdate() + timedelta(days=7)).isoformat(),
        }).status_code, 302)
        self.assertFalse(Mantenimiento.objects.exigibles().exists())
        self.client.post(reverse("cambiar_mantenimiento", args=[orden.pk, "cancelar"]))
        baja = reverse("cambiar_baja", args=[self.activo.pk])
        self.client.post(baja, {"accion": "baja"})
        self.client.post(baja, {"accion": "baja"})
        self.activo.refresh_from_db()
        self.assertEqual(self.activo.estado, Activo.Estado.BAJA)
        self.client.post(baja, {"accion": "reactivar"})
        self.activo.refresh_from_db()
        self.assertEqual(self.activo.estado, Activo.Estado.DISPONIBLE)

    def test_portada_y_aislamiento_de_contratistas(self):
        self.assertContains(self.client.get(reverse("portada")), "Alquiler de herramientas para obras")
        self.assertEqual(self.client.get(reverse("portal_contratista")).status_code, 302)

        otro = Contratista.objects.create(nombre="Montajes Sur", identificador="DEMO-2")
        ahora = timezone.now()
        prestamos = []
        for contratista, activo in ((self.contratista, self.activo), (otro, self.segundo)):
            prestamo = Prestamo.objects.create(
                activo=activo, contratista=contratista, bodega=self.bodega,
                entregado_en=ahora - timedelta(days=2), vence_en=ahora - timedelta(days=1),
                responsable_entrega="Patricia", firma_entrega=firma_prueba(), entrega_por=self.operador,
            )
            prestamos.append(prestamo)
        cuenta = get_user_model().objects.create_user("contratista", password="clave-de-prueba")
        self.contratista.cuenta = cuenta
        self.contratista.save(update_fields=["cuenta"])

        login = self.client.post(reverse("login"), {"username": "contratista", "password": "clave-de-prueba"})
        self.assertRedirects(login, reverse("portal_contratista"))
        portal = self.client.get(reverse("portal_contratista"))
        self.assertContains(portal, "Taladro")
        self.assertContains(portal, "1 devolución vencida")
        self.assertNotContains(portal, "Sierra")
        self.assertNotContains(portal, "Montajes Sur")
        self.assertContains(self.client.get(reverse("portal_contratista"), {"estado": "vencidos"}), "Taladro")
        filtrado = self.client.get(reverse("portal_contratista"), {"estado": "devueltos"})
        self.assertContains(filtrado, "No hay préstamos en este estado")
        self.assertNotContains(filtrado, "Taladro")
        propio = reverse("prestamo_contratista", args=[prestamos[0].pk])
        ajeno = reverse("prestamo_contratista", args=[prestamos[1].pk])
        detalle = self.client.get(propio)
        self.assertContains(detalle, "Taladro")
        self.assertNotContains(detalle, "data:image")
        self.assertIn("no-store", detalle.headers["Cache-Control"])
        self.assertEqual(self.client.get(ajeno).status_code, 404)
        self.assertEqual(self.client.post(propio).status_code, 405)
        self.assertEqual(self.client.get(reverse("prestamos")).status_code, 403)
        self.assertEqual(self.client.get(reverse("prestamo-list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 302)

    def test_catalogo_publico_respeta_publicacion_y_baja(self):
        url = reverse("catalogo_publico")
        self.assertNotContains(self.client.get(url), "<h3>Taladro</h3>", html=True)
        self.client.force_login(self.supervisor)
        editar = reverse("activo_editar", args=[self.activo.pk])
        datos = {
            "codigo": self.activo.codigo, "nombre": self.activo.nombre,
            "descripcion": "Nota interna de bodega", "mostrar_en_catalogo": "on",
        }
        self.assertEqual(self.client.post(editar, datos).status_code, 302)
        Activo.objects.filter(pk=self.segundo.pk).update(mostrar_en_catalogo=True, dado_de_baja=True)
        self.client.logout()
        resultado = self.client.get(url)
        self.assertContains(resultado, "<h3>Taladro</h3>", html=True)
        self.assertNotContains(resultado, "<h3>Sierra</h3>", html=True)
        for dato_privado in ("T-01", "Nota interna", "Obra Norte"):
            self.assertNotContains(resultado, dato_privado)
        self.assertNotContains(self.client.get(url, {"q": "martillo"}), "<h3>Taladro</h3>", html=True)

    def test_pago_demo_desde_catalogo(self):
        url = reverse("pago_simulado", args=["herramientas"])
        servicio = Servicio.objects.get(codigo="herramientas")
        self.activo.servicio = servicio
        self.activo.save(update_fields=["servicio"])
        catalogo = self.client.get(reverse("catalogo_publico"))
        self.assertContains(catalogo, url)
        self.assertContains(catalogo, "Arrendar")
        self.assertNotContains(catalogo, "Simular pago")
        self.assertContains(self.client.get(reverse("catalogo_publico"), {"q": "maquinaria"}), "Maquinaria ligera")
        self.assertNotContains(self.client.get(reverse("catalogo_publico"), {"q": "maquinaria"}), url)
        categoria = self.client.get(reverse("catalogo_publico"), {"categoria": "maquinaria"})
        self.assertNotContains(categoria, url)
        self.assertContains(categoria, reverse("pago_simulado", args=["maquinaria"]))
        self.assertContains(categoria, 'href="?#servicios"')
        self.assertContains(self.client.get(url), "$12.500")
        self.assertEqual(self.client.post(url, {"cantidad": 1}).status_code, 302)
        self.assertFalse(SolicitudServicio.objects.exists())
        cuenta = get_user_model().objects.create_user(
            "cliente", first_name="Ana", last_name="Soto", email="ana@example.com", password="clave-de-prueba",
        )
        self.contratista.cuenta = cuenta
        self.contratista.save(update_fields=["cuenta"])
        self.client.force_login(cuenta)
        form = self.client.get(url).context["form"]
        self.assertEqual(form.initial["nombre"], "Ana")
        self.assertEqual(form.initial["apellido"], "Soto")
        datos = {
            **DATOS_PAGO,
            "token": form.initial["token"], "nombre": "Andrea", "apellido": "Soto",
            "correo": "andrea@example.com", "telefono": "+56 9 1234 5678",
            "fecha": (timezone.localdate() + timedelta(days=2)).isoformat(),
            "direccion": "Calle Nueva 123", "comuna": "Santiago", "region": "Metropolitana",
            "cantidad": 3, "escenario": "aprobado", "tarifa": 1,
        }
        self.assertEqual(self.client.post(url, datos).status_code, 302)
        solicitud = SolicitudServicio.objects.get()
        self.assertEqual(solicitud.total, 37_500)
        self.assertEqual(solicitud.nombre, "Andrea")
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.first_name, "Ana")
        self.assertEqual(servicio.disponibles, 0)
        self.assertEqual(self.client.post(url, datos).status_code, 302)
        self.assertEqual(SolicitudServicio.objects.count(), 1)
        otra = self.client.get(url).context["form"].initial["token"]
        sin_stock = self.client.post(url, {**datos, "token": otra})
        self.assertContains(sin_stock, "Ya no quedan unidades")
        self.client.post(reverse("solicitud_cancelar", args=[solicitud.referencia]))
        self.assertEqual(servicio.disponibles, 1)
        incompleto = self.client.post(url, {"token": otra, "cantidad": 1, "escenario": "aprobado"})
        for campo in ("nombre", "apellido", "correo", "telefono", "fecha", "direccion", "comuna", "region"):
            self.assertIn(campo, incompleto.context["form"].errors)
        invalido = self.client.post(url, {**datos, "token": otra, "fecha": "2020-01-01", "telefono": "123"})
        self.assertIn("fecha", invalido.context["form"].errors)
        self.assertIn("telefono", invalido.context["form"].errors)
        self.assertEqual(self.client.get(reverse("pago_simulado", args=["inexistente"])).status_code, 404)
        protegido = Client(enforce_csrf_checks=True).post(url, {"cantidad": 1, "escenario": "aprobado"})
        self.assertEqual(protegido.status_code, 403)
        self.assertFalse(Prestamo.objects.exists())

    def test_reserva_entrega_devolucion_y_bloqueo_manual(self):
        servicio = Servicio.objects.get(codigo="taladro")
        self.activo.servicio = servicio
        self.activo.save(update_fields=["servicio"])
        datos = {
            **DATOS_PAGO,
            "cantidad": 2, "nombre": "Ana", "apellido": "Soto", "correo": "a@example.com",
            "telefono": "912345678", "fecha": timezone.localdate(), "direccion": "Calle Uno 123",
            "comuna": "Santiago", "region": "Metropolitana", "observaciones": "", "escenario": "aprobado",
        }
        solicitud = services.registrar_solicitud(
            contratista=self.contratista, servicio=servicio, referencia=uuid.uuid4(), datos=datos,
        )
        self.assertEqual(servicio.disponibles, 0)
        prestamo = services.entregar(
            activo=self.activo, contratista=self.contratista, solicitud=solicitud,
            vence_en=timezone.now() + timedelta(days=2), responsable="Ana Soto",
            firma=firma_prueba(), usuario=self.operador,
        )
        self.assertEqual(servicio.disponibles, 0)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, "entregada")
        with self.assertRaises(ValidationError):
            services.cancelar_solicitud(solicitud)
        services.devolver(prestamo=prestamo, horas=1, responsable="Ana", firma=firma_prueba(), usuario=self.operador)
        self.assertEqual(servicio.disponibles, 1)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado_visible, "Devuelto")
        self.contratista.bloqueado_manual = True
        self.contratista.save(update_fields=["bloqueado_manual"])
        with self.assertRaisesMessage(ValidationError, "bloqueada"):
            services.registrar_solicitud(
                contratista=self.contratista, servicio=servicio, referencia=uuid.uuid4(), datos=datos,
            )

    def test_registro_seguro_y_busquedas(self):
        self.assertEqual(self.client.get(reverse("sugerencias_busqueda"), {"q": "ta"}).status_code, 200)
        sugerencias = self.client.get(reverse("sugerencias_busqueda"), {"q": "electrico"}).json()["resultados"]
        self.assertTrue(any(item["nombre"] == "Generador eléctrico" for item in sugerencias))
        registro = {
            "username": "nuevo", "first_name": "Ana", "last_name": "Soto", "email": "ana@example.com",
            "identificador": "12345678-5", "telefono": "912345678", "direccion": "Calle Uno 123",
            "comuna": "Santiago", "region": "Metropolitana",
            "password1": "Buildcorp-2026-seguro!", "password2": "Buildcorp-2026-seguro!",
            "is_staff": "true", "bloqueado_manual": "false",
        }
        response = self.client.post(reverse("registro"), registro)
        self.assertRedirects(response, reverse("portal_contratista"))
        usuario = get_user_model().objects.get(username="nuevo")
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
        form = self.client.get(reverse("pago_simulado", args=["taladro"])).context["form"]
        for campo in ("telefono", "direccion", "comuna", "region"):
            self.assertEqual(form.initial[campo], registro[campo])
        self.assertEqual(form.initial["rut"], "12345678-5")
        self.assertContains(self.client.get(reverse("registro")), "Crear mi cuenta")
        segunda = {**registro, "username": "nueva-cuenta", "identificador": "76086428-5", "email": "otra@example.com"}
        self.assertRedirects(self.client.post(reverse("registro"), segunda), reverse("portal_contratista"))
        cuenta_nueva = get_user_model().objects.get(username="nueva-cuenta")
        self.assertEqual(self.client.session["_auth_user_id"], str(cuenta_nueva.pk))

    def test_factura_pago_transferencia_y_documentos_privados(self):
        cuenta = get_user_model().objects.create_user("comprador", password="clave")
        self.contratista.cuenta = cuenta
        self.contratista.save(update_fields=["cuenta"])
        self.client.force_login(cuenta)
        url = reverse("pago_simulado", args=["traslado"])
        token = self.client.get(url).context["form"].initial["token"]
        datos = {
            **DATOS_PAGO, "token": token, "nombre": "Ana", "apellido": "Soto",
            "correo": "ana@example.com", "telefono": "912345678", "fecha": timezone.localdate().isoformat(),
            "direccion": "Calle Uno 123", "comuna": "Santiago", "region": "Metropolitana",
            "cantidad": 2, "metodo_pago": "transferencia", "tipo_documento": "factura",
        }
        incompleto = self.client.post(url, datos)
        self.assertIn("razon_social", incompleto.context["form"].errors)
        self.assertFalse(SolicitudServicio.objects.exists())
        datos.update(razon_social="Empresa de prueba", rut_facturacion="76086428-5",
                     giro="Construcción", direccion_facturacion="Calle Dos 456, Santiago")
        self.assertEqual(rut_normalizado(datos["rut_facturacion"]), "76086428-5")
        response = self.client.post(url, datos)
        self.assertEqual(response.status_code, 302)
        solicitud = SolicitudServicio.objects.get()
        self.assertEqual(solicitud.metodo_pago, "transferencia")
        self.assertEqual(solicitud.neto + solicitud.iva, solicitud.total)
        self.assertContains(self.client.get(response.url), "El pago se ha realizado con éxito")
        for tipo in ("informe", "factura"):
            ruta = reverse("solicitud_pdf", args=[solicitud.referencia, tipo])
            documento = self.client.get(ruta)
            self.assertEqual(documento["Content-Type"], "application/pdf")
            self.assertTrue(documento.content.startswith(b"%PDF-"))
        otra = get_user_model().objects.create_user("otro-cliente")
        self.client.force_login(otra)
        self.assertEqual(self.client.get(ruta).status_code, 403)
        Contratista.objects.create(nombre="Otra persona", identificador="OTRO-CLIENTE", cuenta=otra)
        self.assertEqual(self.client.get(ruta).status_code, 404)
        with self.assertRaises(ValidationError):
            rut_normalizado("12345678-0")


class ErroresPublicosTests(TestCase):
    def test_ruta_inexistente_y_enlace_de_regreso(self):
        for debug in (True, False):
            with self.settings(DEBUG=debug):
                response = self.client.get("/esta-pagina-no-existe/")
                self.assertContains(response, "Esta página no existe", status_code=404)
                self.assertContains(response, "gato-ayudante.png", status_code=404)
                self.assertContains(response, f'href="{reverse("portada")}"', status_code=404)
                self.assertNotContains(response, "Django", status_code=404)

    @override_settings(DEBUG=True)
    def test_registro_inexistente_y_barras_finales(self):
        response = self.client.get(reverse("pago_simulado", args=["inexistente"]))
        self.assertContains(response, "Esta página no existe", status_code=404)
        catalogo = reverse("catalogo_publico")
        self.assertRedirects(
            self.client.get(catalogo.rstrip("/")), catalogo,
            status_code=301, fetch_redirect_response=False,
        )

    def test_formulario_vencido_y_api(self):
        response = Client(enforce_csrf_checks=True).post(
            reverse("pago_simulado", args=["herramientas"]), {"cantidad": 1, "escenario": "aprobado"},
        )
        self.assertContains(response, "Vuelve a abrir el formulario", status_code=403)
        api_url = reverse("activo-list") + "ruta/inexistente/"
        response = self.client.get(api_url)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Esta página no existe"})

    def test_error_de_servidor_se_muestra_sin_base_de_datos(self):
        from buildcorp.errors import error_servidor

        with self.assertNumQueries(0):
            response = error_servidor(RequestFactory().get("/"))
        self.assertContains(response, "Tenemos un problema en el taller", status_code=500)


@skipUnless(connection.vendor == "postgresql", "Requiere bloqueo de filas de PostgreSQL.")
class EntregasConcurrentesTests(TransactionTestCase):
    def test_una_unidad_no_se_reserva_dos_veces(self):
        servicio = Servicio.objects.create(
            codigo="prueba-concurrente", nombre="Taladro", categoria="Herramientas",
            descripcion="Prueba", unidad="día", tarifa=5000,
        )
        obra = Obra.objects.create(nombre="Obra de reserva", direccion="Calle Uno")
        bodega = Bodega.objects.create(obra=obra, nombre="Central")
        Activo.objects.create(codigo="RES-1", nombre="Taladro", bodega=bodega, servicio=servicio)
        contratistas = [
            Contratista.objects.create(nombre=f"Empresa {i}", identificador=f"RES-{i}")
            for i in (1, 2)
        ]
        datos = {
            **DATOS_PAGO,
            "cantidad": 1, "nombre": "Ana", "apellido": "Soto", "correo": "a@example.com",
            "telefono": "912345678", "fecha": timezone.localdate(), "direccion": "Calle Uno 123",
            "comuna": "Santiago", "region": "Metropolitana", "observaciones": "", "escenario": "aprobado",
        }
        barrera = Barrier(2, timeout=5)

        def reservar(contratista):
            try:
                barrera.wait()
                services.registrar_solicitud(
                    contratista=contratista, servicio=servicio, referencia=uuid.uuid4(), datos=datos,
                )
                return True
            except ValidationError as error:
                self.assertIn("Ya no quedan unidades", error.messages[0])
                return False
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as equipo:
            self.assertCountEqual(list(equipo.map(reservar, contratistas)), [True, False])
        self.assertEqual(SolicitudServicio.objects.count(), 1)
        self.assertEqual(servicio.disponibles, 0)

    def test_solo_una_entrega_por_herramienta(self):
        cuenta = get_user_model().objects.create_user("bodega")
        obra = Obra.objects.create(nombre="Obra Centro", direccion="Calle Uno")
        bodega = Bodega.objects.create(obra=obra, nombre="Principal")
        activo = Activo.objects.create(codigo="T-01", nombre="Taladro", bodega=bodega)
        contratistas = [
            Contratista.objects.create(nombre=f"Contratista {i}", identificador=f"C-{i}")
            for i in (1, 2)
        ]
        firma = firma_prueba()
        barrera = Barrier(2, timeout=5)

        def entregar(contratista):
            try:
                barrera.wait()
                services.entregar(
                    activo=activo, contratista=contratista, vence_en=timezone.now() + timedelta(days=1),
                    responsable="Patricia", firma=firma, usuario=cuenta,
                )
                return True
            except ValidationError as error:
                self.assertEqual(error.messages, ["La herramienta ya no está disponible."])
                return False
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as equipo:
            resultados = list(equipo.map(entregar, contratistas))

        self.assertCountEqual(resultados, [True, False])
        self.assertEqual(Prestamo.objects.abiertos().count(), 1)
