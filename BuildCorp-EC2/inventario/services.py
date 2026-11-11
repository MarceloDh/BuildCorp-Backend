from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Activo, Contratista, Mantenimiento, Prestamo, Servicio, SolicitudServicio, Traslado
from .validaciones import rut_normalizado


@transaction.atomic
def registrar_solicitud(*, contratista, servicio, referencia, datos):
    contratista = Contratista.objects.select_for_update().get(pk=contratista.pk)
    campos = {
        campo: datos[campo] for campo in (
            "cantidad", "nombre", "apellido", "correo", "telefono", "fecha",
            "direccion", "comuna", "region", "observaciones",
            "rut", "metodo_pago", "tipo_documento", "razon_social", "rut_facturacion",
            "giro", "direccion_facturacion",
        )
    }
    campos.update(
        contratista=contratista, catalogo=servicio, codigo_servicio=servicio.codigo, servicio=servicio.nombre,
        tarifa=servicio.tarifa, total=servicio.tarifa * campos["cantidad"],
        pago_aprobado=datos["escenario"] == "aprobado",
    )
    campos["rut"] = rut_normalizado(campos["rut"])
    if campos["metodo_pago"] not in SolicitudServicio.MetodoPago.values:
        raise ValidationError("Selecciona un medio de pago.")
    if campos["tipo_documento"] == "factura":
        if not all(campos[campo] for campo in ("razon_social", "rut_facturacion", "giro", "direccion_facturacion")):
            raise ValidationError("Completa los datos de facturación.")
        campos["rut_facturacion"] = rut_normalizado(campos["rut_facturacion"])
    existente = SolicitudServicio.objects.filter(referencia=referencia).first()
    if existente:
        if any(getattr(existente, campo) != valor for campo, valor in campos.items()):
            raise ValidationError("Esta solicitud ya se envió con otros datos. Abre el servicio de nuevo.")
        return existente
    if contratista.bloqueado_manual:
        raise ValidationError("Tu cuenta está bloqueada para nuevos arriendos. Contacta a BuildCorp.")
    if contratista.prestamos.vencidos().exists():
        raise ValidationError("Tienes devoluciones vencidas. Coordina con bodega antes de solicitar otro servicio.")
    actual = Servicio.objects.select_for_update().get(pk=servicio.pk)
    if not actual.publicado or actual.tarifa != servicio.tarifa:
        raise ValidationError("Este servicio cambió. Abre el catálogo de nuevo para revisar sus condiciones.")
    if actual.requiere_equipo and campos["pago_aprobado"]:
        activo = Activo.objects.disponibles().filter(servicio=actual).select_for_update().first()
        if activo is None or not Activo.objects.disponibles().filter(pk=activo.pk).exists():
            raise ValidationError("Ya no quedan unidades disponibles. Prueba con otro equipo.")
        campos["activo"] = activo
    solicitud = SolicitudServicio(referencia=referencia, **campos)
    solicitud.full_clean()
    solicitud.save()
    return solicitud


@transaction.atomic
def entregar(*, activo, contratista, vence_en, responsable, firma, usuario, solicitud=None):
    contratista = Contratista.objects.select_for_update().get(pk=contratista.pk)
    activo = Activo.objects.select_for_update().get(pk=activo.pk)
    ahora = timezone.now()
    if vence_en <= ahora:
        raise ValidationError("La fecha de devolución debe ser posterior a la entrega.")
    if contratista.prestamos.vencidos().exists():
        raise ValidationError("El contratista tiene devoluciones vencidas. Registra la devolución pendiente.")
    if contratista.bloqueado_manual:
        raise ValidationError("El contratista está bloqueado por administración.")
    if solicitud is not None:
        solicitud = SolicitudServicio.objects.select_for_update().get(pk=solicitud.pk)
        if (
            solicitud.activo_id != activo.pk or solicitud.contratista_id != contratista.pk
            or solicitud.estado != "pendiente" or not solicitud.pago_aprobado
        ):
            raise ValidationError("La reserva no corresponde a esta entrega o ya fue procesada.")
    estado_esperado = Activo.Estado.RESERVADO if solicitud else Activo.Estado.DISPONIBLE
    if activo.estado != estado_esperado:
        raise ValidationError("La herramienta ya no está disponible.")
    if activo.mantenimientos.exigibles().exists():
        raise ValidationError("La herramienta tiene un mantenimiento pendiente que ya corresponde realizar.")
    prestamo = Prestamo.objects.create(
        activo=activo, contratista=contratista, bodega_id=activo.bodega_id, vence_en=vence_en,
        entregado_en=ahora, responsable_entrega=responsable, firma_entrega=firma, entrega_por=usuario,
        solicitud=solicitud,
    )
    if solicitud:
        solicitud.estado = SolicitudServicio.Estado.ENTREGADA
        solicitud.save(update_fields=["estado"])
    return prestamo


@transaction.atomic
def cancelar_solicitud(solicitud):
    Contratista.objects.select_for_update().get(pk=solicitud.contratista_id)
    if solicitud.activo_id:
        Activo.objects.select_for_update().get(pk=solicitud.activo_id)
    solicitud = SolicitudServicio.objects.select_for_update().get(pk=solicitud.pk)
    if solicitud.estado == SolicitudServicio.Estado.ENTREGADA:
        raise ValidationError("La herramienta ya fue entregada. Registra su devolución en bodega.")
    solicitud.estado = SolicitudServicio.Estado.CANCELADA
    solicitud.save(update_fields=["estado"])


@transaction.atomic
def devolver(*, prestamo, horas, responsable, firma, usuario):
    Contratista.objects.select_for_update().get(pk=prestamo.contratista_id)
    activo = Activo.objects.select_for_update().get(pk=prestamo.activo_id)
    prestamo = Prestamo.objects.select_for_update().get(pk=prestamo.pk)
    if prestamo.devuelto_en is not None:
        raise ValidationError("Esta devolución ya fue registrada.")
    prestamo.devuelto_en = timezone.now()
    prestamo.responsable_devolucion = responsable
    prestamo.firma_devolucion = firma
    prestamo.devolucion_por = usuario
    prestamo.horas_utilizadas = horas
    prestamo.save(update_fields=[
        "devuelto_en", "responsable_devolucion", "firma_devolucion",
        "devolucion_por", "horas_utilizadas",
    ])
    activo.horas_uso += horas
    activo.save(update_fields=["horas_uso"])


@transaction.atomic
def trasladar(*, activo, destino, usuario):
    activo = Activo.objects.select_for_update().get(pk=activo.pk)
    if activo.estado != Activo.Estado.DISPONIBLE:
        raise ValidationError("Solo se pueden trasladar herramientas disponibles.")
    if activo.bodega_id == destino.pk:
        raise ValidationError("Selecciona una bodega distinta a la de origen.")
    Traslado.objects.create(activo=activo, origen_id=activo.bodega_id, destino=destino, registrado_por=usuario)
    activo.bodega = destino
    activo.save(update_fields=["bodega"])


@transaction.atomic
def cambiar_baja(activo, dar_de_baja):
    activo = Activo.objects.select_for_update().get(pk=activo.pk)
    if activo.dado_de_baja == dar_de_baja:
        return
    if dar_de_baja:
        if activo.estado != Activo.Estado.DISPONIBLE:
            raise ValidationError("Cierra el préstamo o mantenimiento antes de dar de baja la herramienta.")
        if activo.mantenimientos.pendientes().exists():
            raise ValidationError("Cancela o completa los mantenimientos programados antes de dar de baja.")
    activo.dado_de_baja = dar_de_baja
    activo.save(update_fields=["dado_de_baja"])


@transaction.atomic
def programar(*, activo, tarea, fecha_limite, horas_limite, observaciones, registro=None):
    activo = Activo.objects.select_for_update().get(pk=activo.pk)
    if activo.dado_de_baja:
        raise ValidationError("La herramienta está dada de baja.")
    if registro is None:
        mantenimiento = Mantenimiento(activo=activo)
    else:
        mantenimiento = Mantenimiento.objects.select_for_update().get(pk=registro.pk, activo=activo)
        if mantenimiento.estado != Mantenimiento.Estado.PROGRAMADO:
            raise ValidationError("Solo se pueden editar mantenimientos programados.")
    mantenimiento.tarea = tarea
    mantenimiento.fecha_limite = fecha_limite
    mantenimiento.horas_limite = horas_limite
    mantenimiento.observaciones = observaciones
    mantenimiento.full_clean()
    mantenimiento.save()


@transaction.atomic
def cambiar_mantenimiento(mantenimiento, accion):
    activo = Activo.objects.select_for_update().get(pk=mantenimiento.activo_id)
    mantenimiento = Mantenimiento.objects.select_for_update().get(pk=mantenimiento.pk)
    programado = mantenimiento.estado == Mantenimiento.Estado.PROGRAMADO
    en_curso = mantenimiento.estado == Mantenimiento.Estado.EN_CURSO
    if accion == "iniciar" and programado:
        if activo.estado != Activo.Estado.DISPONIBLE:
            raise ValidationError("La herramienta debe estar disponible para entrar a mantenimiento.")
        mantenimiento.estado = Mantenimiento.Estado.EN_CURSO
        mantenimiento.iniciado_en = timezone.now()
    elif accion == "completar" and en_curso:
        mantenimiento.estado = Mantenimiento.Estado.COMPLETADO
        mantenimiento.cerrado_en = timezone.now()
    elif accion == "cancelar" and (programado or en_curso):
        mantenimiento.estado = Mantenimiento.Estado.CANCELADO
        mantenimiento.cerrado_en = timezone.now()
    else:
        raise ValidationError("La acción no corresponde al estado actual del mantenimiento.")
    mantenimiento.save(update_fields=["estado", "iniciado_en", "cerrado_en"])
