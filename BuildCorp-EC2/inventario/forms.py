import base64
import binascii
from io import BytesIO

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.validators import RegexValidator
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.db import transaction
from PIL import Image, ImageChops

from .models import Activo, Bodega, Contratista, SolicitudServicio
from .validaciones import rut_normalizado


class FirmaField(forms.CharField):
    widget = forms.HiddenInput

    def __init__(self):
        super().__init__(max_length=80_000, label="Firma del responsable",
                         error_messages={"required": "Dibuja la firma del responsable."})

    def clean(self, value):
        value = super().clean(value)
        prefix = "data:image/png;base64,"
        if not value.startswith(prefix):
            raise ValidationError("La firma debe dibujarse en el recuadro.")
        try:
            data = base64.b64decode(value[len(prefix):], validate=True)
            with Image.open(BytesIO(data), formats=["PNG"]) as image:
                if image.size != (640, 200):
                    raise ValueError
                rgba = image.convert("RGBA")
                fondo = Image.new("RGBA", rgba.size, "white")
                fondo.alpha_composite(rgba)
                fondo = fondo.convert("RGB")
                if not ImageChops.difference(fondo, Image.new("RGB", fondo.size, "white")).getbbox():
                    raise ValueError
        except (ValueError, OSError, binascii.Error, Image.DecompressionBombError):
            raise ValidationError("La firma está vacía o no es válida.") from None
        return value


class EntregaForm(forms.Form):
    solicitud = forms.ModelChoiceField(
        queryset=SolicitudServicio.objects.filter(estado="pendiente", pago_aprobado=True),
        required=False, widget=forms.HiddenInput,
    )
    activo = forms.ModelChoiceField(queryset=Activo.objects.filter(dado_de_baja=False))
    contratista = forms.ModelChoiceField(queryset=Contratista.objects.all())
    vence_en = forms.DateTimeField(
        label="Devolver antes de", widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    responsable = forms.CharField(label="Responsable de obra", max_length=120)
    firma = FirmaField()


class DevolucionForm(forms.Form):
    horas = forms.IntegerField(label="Horas de uso durante el préstamo", min_value=0, max_value=100_000)
    responsable = forms.CharField(label="Responsable de obra", max_length=120)
    firma = FirmaField()


class TrasladoForm(forms.Form):
    destino = forms.ModelChoiceField(label="Bodega de destino", queryset=Bodega.objects.all())


class PagoSimuladoForm(forms.Form):
    token = forms.CharField(max_length=512, widget=forms.HiddenInput)
    nombre = forms.CharField(label="Nombre", max_length=80, widget=forms.TextInput(attrs={"autocomplete": "given-name"}))
    apellido = forms.CharField(label="Apellido", max_length=80, widget=forms.TextInput(attrs={"autocomplete": "family-name"}))
    rut = forms.CharField(label="RUT", max_length=12, help_text="Con dígito verificador, por ejemplo 12.345.678-5.")
    correo = forms.EmailField(label="Correo electrónico", widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    telefono = forms.CharField(
        label="Teléfono de contacto", max_length=25,
        validators=[RegexValidator(r"^\+?[0-9 ()-]{8,25}$", "Escribe un teléfono válido con su código de área.")],
        widget=forms.TextInput(attrs={"type": "tel", "autocomplete": "tel"}),
    )
    fecha = forms.DateField(label="Fecha del servicio", widget=forms.DateInput(attrs={"type": "date"}))
    direccion = forms.CharField(label="Dirección de la obra", min_length=5, max_length=200,
                               widget=forms.TextInput(attrs={"autocomplete": "street-address"}))
    comuna = forms.CharField(label="Comuna", max_length=80,
                            widget=forms.TextInput(attrs={"autocomplete": "address-level2"}))
    region = forms.CharField(label="Región", max_length=80,
                            widget=forms.TextInput(attrs={"autocomplete": "address-level1"}))
    observaciones = forms.CharField(label="Indicaciones de acceso (opcional)", required=False, max_length=1000,
                                    widget=forms.Textarea(attrs={"rows": 2}))
    cantidad = forms.IntegerField(label="Cantidad", min_value=1, max_value=30, initial=1)
    metodo_pago = forms.ChoiceField(label="Medio de pago", choices=SolicitudServicio.MetodoPago, widget=forms.RadioSelect)
    tipo_documento = forms.ChoiceField(
        label="Documento", choices=SolicitudServicio.Documento, initial=SolicitudServicio.Documento.COMPROBANTE,
    )
    razon_social = forms.CharField(label="Razón social", max_length=150, required=False)
    rut_facturacion = forms.CharField(label="RUT de facturación", max_length=12, required=False)
    giro = forms.CharField(label="Giro", max_length=150, required=False)
    direccion_facturacion = forms.CharField(label="Dirección de facturación", max_length=250, required=False)
    escenario = forms.ChoiceField(
        label="Resultado de la simulación",
        choices=(("aprobado", "Pago aprobado"), ("rechazado", "Pago rechazado")),
        initial="aprobado", required=False, widget=forms.HiddenInput,
    )

    def clean_rut(self):
        return rut_normalizado(self.cleaned_data["rut"])

    def clean_escenario(self):
        return self.cleaned_data.get("escenario") or "aprobado"

    def clean(self):
        datos = super().clean()
        campos = ("razon_social", "rut_facturacion", "giro", "direccion_facturacion")
        if datos.get("tipo_documento") == "factura":
            for campo in campos:
                if not datos.get(campo):
                    self.add_error(campo, "Completa este dato para solicitar factura.")
            if datos.get("rut_facturacion"):
                try:
                    datos["rut_facturacion"] = rut_normalizado(datos["rut_facturacion"])
                except ValidationError as error:
                    self.add_error("rut_facturacion", error)
        else:
            for campo in campos:
                datos[campo] = ""
        return datos

    def clean_fecha(self):
        fecha = self.cleaned_data["fecha"]
        if fecha < timezone.localdate():
            raise ValidationError("Elige la fecha de hoy o una fecha futura.")
        return fecha

    def clean_telefono(self):
        telefono = self.cleaned_data["telefono"]
        if not 8 <= sum(caracter.isdigit() for caracter in telefono) <= 15:
            raise ValidationError("El teléfono debe contener entre 8 y 15 dígitos.")
        return telefono


class ProgramacionForm(forms.Form):
    tarea = forms.CharField(max_length=150)
    fecha_limite = forms.DateField(
        label="Fecha límite", required=False, widget=forms.DateInput(attrs={"type": "date"}),
    )
    horas_limite = forms.IntegerField(
        label="Horas acumuladas límite", required=False, min_value=1, max_value=1_000_000,
    )
    observaciones = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("fecha_limite") is None and cleaned.get("horas_limite") is None:
            raise ValidationError("Indica una fecha límite, un límite de horas o ambos.")
        return cleaned


class RegistroContratistaForm(UserCreationForm):
    first_name = forms.CharField(label="Nombre", max_length=80)
    last_name = forms.CharField(label="Apellido", max_length=80)
    email = forms.EmailField(label="Correo electrónico")
    identificador = forms.CharField(label="RUT", max_length=12, help_text="Ejemplo 12.345.678-5.")
    telefono = forms.CharField(label="Teléfono", max_length=25,
                              validators=PagoSimuladoForm.base_fields["telefono"].validators)
    direccion = forms.CharField(label="Dirección habitual de obra", min_length=5, max_length=200)
    comuna = forms.CharField(label="Comuna", max_length=80)
    region = forms.CharField(label="Región", max_length=80)

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "first_name", "last_name", "email")

    def clean_identificador(self):
        valor = rut_normalizado(self.cleaned_data["identificador"])
        existentes = Contratista.objects.values_list("identificador", flat=True)
        if any(item.upper().replace(".", "").replace(" ", "") == valor for item in existentes):
            raise ValidationError("Este identificador ya tiene un registro. Contacta a BuildCorp para acceder.")
        return valor

    def clean_telefono(self):
        return PagoSimuladoForm.clean_telefono(self)

    @transaction.atomic
    def save(self):
        usuario = super().save()
        Contratista.objects.create(
            cuenta=usuario, nombre=usuario.get_full_name(), identificador=self.cleaned_data["identificador"],
            contacto=usuario.email, **{campo: self.cleaned_data[campo] for campo in (
                "telefono", "direccion", "comuna", "region",
            )},
        )
        return usuario
