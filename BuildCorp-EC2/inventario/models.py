from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
import uuid
from decimal import Decimal, ROUND_HALF_UP
from .validaciones import rut_normalizado


class Obra(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    direccion = models.CharField("dirección", max_length=200)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Bodega(models.Model):
    obra = models.ForeignKey(Obra, on_delete=models.PROTECT, related_name="bodegas")
    nombre = models.CharField(max_length=100)

    class Meta:
        ordering = ["obra__nombre", "nombre"]
        constraints = [
            models.UniqueConstraint(fields=["obra", "nombre"], name="bodega_nombre_por_obra"),
        ]

    def __str__(self):
        return f"{self.obra} / {self.nombre}"


class Contratista(models.Model):
    nombre = models.CharField(max_length=120)
    identificador = models.CharField("RUT o identificador", max_length=30, unique=True)
    contacto = models.EmailField(blank=True)
    telefono = models.CharField(max_length=25, blank=True)
    direccion = models.CharField(max_length=200, blank=True)
    comuna = models.CharField(max_length=80, blank=True)
    region = models.CharField(max_length=80, blank=True)
    bloqueado_manual = models.BooleanField("bloqueado por administración", default=False)
    motivo_bloqueo = models.CharField(max_length=250, blank=True)
    cuenta = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="perfil_contratista", verbose_name="cuenta de acceso",
    )

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.identificador})"


class Servicio(models.Model):
    codigo = models.SlugField(unique=True)
    nombre = models.CharField(max_length=120)
    categoria = models.CharField(max_length=20, choices=[
        ("Herramientas", "Herramientas"), ("Maquinaria", "Maquinaria"), ("Logística", "Logística"),
    ])
    descripcion = models.TextField()
    unidad = models.CharField(max_length=10, choices=[("día", "Día"), ("viaje", "Viaje"), ("visita", "Visita")])
    tarifa = models.PositiveIntegerField()
    publicado = models.BooleanField(default=True)

    class Meta:
        ordering = ["pk"]

    @property
    def grupo(self):
        return {"Herramientas": "herramientas", "Maquinaria": "maquinaria", "Logística": "traslado"}[self.categoria]

    @property
    def requiere_equipo(self):
        return self.categoria != "Logística"

    @property
    def tarifa_visible(self):
        from .servicios_demo import pesos
        return pesos(self.tarifa)

    @property
    def disponibles(self):
        return self.activos.disponibles().count()

    def __str__(self):
        return self.nombre


class SolicitudServicio(models.Model):
    class MetodoPago(models.TextChoices):
        WEBPAY = "webpay", "Webpay"
        TRANSFERENCIA = "transferencia", "Transferencia bancaria"

    class Documento(models.TextChoices):
        COMPROBANTE = "comprobante", "Comprobante"
        FACTURA = "factura", "Factura"

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente de entrega"
        ENTREGADA = "entregada", "Entregada"
        CANCELADA = "cancelada", "Cancelada"

    referencia = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    catalogo = models.ForeignKey(Servicio, on_delete=models.PROTECT, related_name="solicitudes")
    activo = models.ForeignKey("Activo", on_delete=models.PROTECT, null=True, blank=True, related_name="solicitudes")
    estado = models.CharField(max_length=15, choices=Estado, default=Estado.PENDIENTE)
    contratista = models.ForeignKey(Contratista, on_delete=models.PROTECT, related_name="solicitudes")
    codigo_servicio = models.CharField(max_length=50)
    servicio = models.CharField(max_length=120)
    tarifa = models.PositiveIntegerField()
    cantidad = models.PositiveSmallIntegerField()
    total = models.PositiveIntegerField()
    nombre = models.CharField(max_length=80)
    apellido = models.CharField(max_length=80)
    rut = models.CharField("RUT del contacto", max_length=12, blank=True, validators=[rut_normalizado])
    correo = models.EmailField()
    telefono = models.CharField(max_length=25)
    fecha = models.DateField()
    direccion = models.CharField(max_length=200)
    comuna = models.CharField(max_length=80)
    region = models.CharField(max_length=80)
    observaciones = models.TextField(blank=True, max_length=1000)
    creada_en = models.DateTimeField(default=timezone.now)
    pago_aprobado = models.BooleanField(default=False)
    metodo_pago = models.CharField(max_length=20, choices=MetodoPago, blank=True)
    tipo_documento = models.CharField(max_length=15, choices=Documento, default=Documento.COMPROBANTE)
    razon_social = models.CharField(max_length=150, blank=True)
    rut_facturacion = models.CharField(max_length=12, blank=True, validators=[rut_normalizado])
    giro = models.CharField(max_length=150, blank=True)
    direccion_facturacion = models.CharField(max_length=250, blank=True)

    @property
    def numero_documento(self):
        return f"BC-{self.pk:06d}"

    @property
    def neto(self):
        return int((Decimal(self.total) / Decimal("1.19")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    @property
    def iva(self):
        return self.total - self.neto

    class Meta:
        ordering = ["-creada_en"]
        constraints = [
            models.CheckConstraint(condition=Q(cantidad__gte=1, cantidad__lte=30), name="solicitud_cantidad_valida"),
            models.CheckConstraint(condition=Q(total=F("tarifa") * F("cantidad")), name="solicitud_total_valido"),
            models.UniqueConstraint(
                fields=["activo"], condition=Q(estado="pendiente", pago_aprobado=True),
                name="una_reserva_por_activo",
            ),
        ]

    @property
    def estado_visible(self):
        if self.estado == self.Estado.CANCELADA:
            return "Cancelada"
        if not self.pago_aprobado:
            return "Pago de prueba rechazado"
        if self.estado == self.Estado.ENTREGADA:
            prestamo = getattr(self, "prestamo", None)
            if prestamo and prestamo.devuelto_en:
                return "Devuelto"
        return self.get_estado_display()

    def __str__(self):
        return f"{self.servicio} · {self.contratista.nombre}"


class ActivoQuerySet(models.QuerySet):
    def disponibles(self):
        return self.filter(dado_de_baja=False).exclude(
            pk__in=Prestamo.objects.abiertos().values("activo"),
        ).exclude(
            pk__in=Mantenimiento.objects.filter(
                Q(estado="en_curso") | (
                    Q(estado="programado") & (
                        Q(fecha_limite__lte=timezone.localdate()) | Q(horas_limite__lte=F("activo__horas_uso"))
                    )
                )
            ).values("activo"),
        ).exclude(
            pk__in=SolicitudServicio.objects.filter(
                estado="pendiente", pago_aprobado=True, activo__isnull=False,
            ).values("activo"),
        )


class Activo(models.Model):
    class Estado(models.TextChoices):
        DISPONIBLE = "disponible", "Disponible"
        RESERVADO = "reservado", "Reservado"
        EN_USO = "en_uso", "En uso"
        MANTENIMIENTO = "mantenimiento", "Mantenimiento"
        BAJA = "baja", "Dado de baja"

    codigo = models.CharField("código", max_length=30, unique=True)
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField("descripción", blank=True)
    mostrar_en_catalogo = models.BooleanField(
        "mostrar en el catálogo público", default=False,
        help_text="Publica únicamente el nombre de la herramienta mientras esté activa.",
    )
    bodega = models.ForeignKey(Bodega, on_delete=models.PROTECT, related_name="activos")
    servicio = models.ForeignKey(Servicio, on_delete=models.PROTECT, null=True, blank=True, related_name="activos")
    horas_uso = models.PositiveIntegerField("horas acumuladas", default=0)
    dado_de_baja = models.BooleanField(default=False)
    objects = ActivoQuerySet.as_manager()

    class Meta:
        ordering = ["codigo"]

    @property
    def estado(self):
        if self.dado_de_baja:
            return self.Estado.BAJA
        if self.prestamos.filter(devuelto_en__isnull=True).exists():
            return self.Estado.EN_USO
        if self.mantenimientos.filter(estado=Mantenimiento.Estado.EN_CURSO).exists():
            return self.Estado.MANTENIMIENTO
        if self.solicitudes.filter(estado="pendiente", pago_aprobado=True).exists():
            return self.Estado.RESERVADO
        return self.Estado.DISPONIBLE

    @property
    def estado_visible(self):
        return self.Estado(self.estado).label

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"


class Traslado(models.Model):
    activo = models.ForeignKey(Activo, on_delete=models.PROTECT, related_name="traslados")
    origen = models.ForeignKey(Bodega, on_delete=models.PROTECT, related_name="+")
    destino = models.ForeignKey(Bodega, on_delete=models.PROTECT, related_name="+")
    registrado_en = models.DateTimeField(default=timezone.now)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        ordering = ["-registrado_en"]
        constraints = [
            models.CheckConstraint(condition=~Q(origen=F("destino")), name="traslado_entre_bodegas"),
        ]

    def __str__(self):
        return f"{self.activo} → {self.destino}"


class PrestamoQuerySet(models.QuerySet):
    def abiertos(self):
        return self.filter(devuelto_en__isnull=True)

    def vencidos(self):
        return self.abiertos().filter(vence_en__lt=timezone.now())


class Prestamo(models.Model):
    solicitud = models.OneToOneField(
        SolicitudServicio, on_delete=models.PROTECT, null=True, blank=True, related_name="prestamo",
    )
    activo = models.ForeignKey(Activo, on_delete=models.PROTECT, related_name="prestamos")
    contratista = models.ForeignKey(Contratista, on_delete=models.PROTECT, related_name="prestamos")
    bodega = models.ForeignKey(Bodega, on_delete=models.PROTECT, related_name="prestamos")
    entregado_en = models.DateTimeField(default=timezone.now)
    vence_en = models.DateTimeField("devolver antes de")
    responsable_entrega = models.CharField("responsable de obra", max_length=120)
    firma_entrega = models.TextField()
    entrega_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    devuelto_en = models.DateTimeField(null=True, blank=True)
    responsable_devolucion = models.CharField("responsable de obra", max_length=120, blank=True)
    firma_devolucion = models.TextField(blank=True)
    devolucion_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", null=True, blank=True,
    )
    horas_utilizadas = models.PositiveIntegerField(null=True, blank=True)

    objects = PrestamoQuerySet.as_manager()

    class Meta:
        ordering = ["-entregado_en"]
        constraints = [
            models.UniqueConstraint(
                fields=["activo"], condition=Q(devuelto_en__isnull=True), name="prestamo_abierto_por_activo",
            ),
            models.CheckConstraint(condition=Q(vence_en__gt=F("entregado_en")), name="prestamo_plazo_valido"),
        ]

    @property
    def vencido(self):
        return self.devuelto_en is None and self.vence_en < timezone.now()

    @property
    def estado_visible(self):
        if self.devuelto_en:
            return "Devuelto"
        return "Vencido" if self.vencido else "Vigente"

    def __str__(self):
        return f"{self.activo} / {self.contratista}"


class MantenimientoQuerySet(models.QuerySet):
    def pendientes(self):
        return self.filter(estado=Mantenimiento.Estado.PROGRAMADO)

    def exigibles(self):
        return self.pendientes().filter(
            Q(fecha_limite__lte=timezone.localdate()) | Q(horas_limite__lte=F("activo__horas_uso"))
        )


class Mantenimiento(models.Model):
    class Estado(models.TextChoices):
        PROGRAMADO = "programado", "Programado"
        EN_CURSO = "en_curso", "En curso"
        COMPLETADO = "completado", "Completado"
        CANCELADO = "cancelado", "Cancelado"

    activo = models.ForeignKey(Activo, on_delete=models.PROTECT, related_name="mantenimientos")
    tarea = models.CharField(max_length=150)
    fecha_limite = models.DateField("fecha límite", null=True, blank=True)
    horas_limite = models.PositiveIntegerField("horas acumuladas límite", null=True, blank=True)
    estado = models.CharField(max_length=15, choices=Estado, default=Estado.PROGRAMADO)
    iniciado_en = models.DateTimeField(null=True, blank=True)
    cerrado_en = models.DateTimeField(null=True, blank=True)
    observaciones = models.TextField(blank=True)

    objects = MantenimientoQuerySet.as_manager()

    class Meta:
        ordering = ["-pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(fecha_limite__isnull=False) | Q(horas_limite__isnull=False),
                name="mantenimiento_con_umbral",
            ),
            models.UniqueConstraint(
                fields=["activo"], condition=Q(estado="en_curso"), name="un_mantenimiento_en_curso",
            ),
        ]

    def __str__(self):
        return f"{self.activo} / {self.tarea}"
