import logging

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.urls import include, path
from rest_framework import permissions, routers, serializers, status, viewsets
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .access import puede_operar, puede_supervisar
from .models import Activo, Bodega, Contratista, Mantenimiento, Obra, Prestamo, Traslado
from .services import devolver, entregar, programar, trasladar

logger = logging.getLogger(__name__)


class Conflicto(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "El registro tiene dependencias o cambió durante la operación."


class PermisosInventario(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return puede_operar(request.user)
        return puede_supervisar(request.user)


class ObraSerializer(serializers.ModelSerializer):
    class Meta:
        model = Obra
        fields = ("id", "nombre", "direccion")


class BodegaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bodega
        fields = ("id", "nombre", "obra")

    def validate_obra(self, obra):
        if self.instance and self.instance.obra_id != obra.pk:
            raise serializers.ValidationError("La obra de una bodega existente se conserva.")
        return obra


class HerramientaSerializer(serializers.ModelSerializer):
    estado = serializers.CharField(read_only=True)

    class Meta:
        model = Activo
        fields = ("id", "codigo", "nombre", "descripcion", "bodega", "horas_uso", "estado")
        read_only_fields = ("horas_uso",)

    def validate_bodega(self, bodega):
        if self.instance and self.instance.bodega_id != bodega.pk:
            raise serializers.ValidationError("Usa el flujo de traslado para cambiar la bodega.")
        return bodega


class MantenimientoSerializer(serializers.ModelSerializer):
    horas_limite = serializers.IntegerField(min_value=1, max_value=1_000_000, allow_null=True, required=False)
    observaciones = serializers.CharField(max_length=2000, allow_blank=True, required=False)

    class Meta:
        model = Mantenimiento
        fields = ("id", "activo", "tarea", "fecha_limite", "horas_limite", "observaciones", "estado")
        read_only_fields = ("estado",)

    def validate_activo(self, activo):
        if self.instance and self.instance.activo_id != activo.pk:
            raise serializers.ValidationError("La herramienta de un mantenimiento existente se conserva.")
        return activo

    def validate(self, attrs):
        fecha = attrs.get("fecha_limite", getattr(self.instance, "fecha_limite", None))
        horas = attrs.get("horas_limite", getattr(self.instance, "horas_limite", None))
        if fecha is None and horas is None:
            raise serializers.ValidationError("Indica una fecha límite o un umbral de horas.")
        return attrs

    def create(self, validated_data):
        return self.guardar(validated_data)

    def update(self, instance, validated_data):
        return self.guardar(validated_data, instance)

    def guardar(self, attrs, instance=None):
        campos = ("activo", "tarea", "fecha_limite", "horas_limite", "observaciones")
        valores = {campo: getattr(instance, campo, None) for campo in campos}
        if instance is None:
            valores["observaciones"] = ""
        valores.update(attrs)
        try:
            return programar(**valores, registro=instance)
        except (Activo.DoesNotExist, Mantenimiento.DoesNotExist) as error:
            raise Conflicto() from error
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from error


class InventarioCRUD(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [PermisosInventario]

    def create(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                return super().create(request, *args, **kwargs)
        except IntegrityError as error:
            raise Conflicto() from error

    def update(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                return super().update(request, *args, **kwargs)
        except IntegrityError as error:
            raise Conflicto() from error

    def destroy(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                return super().destroy(request, *args, **kwargs)
        except (ProtectedError, IntegrityError) as error:
            raise Conflicto() from error

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action in ("update", "partial_update", "destroy"):
            return queryset.select_for_update(of=("self",))
        return queryset


class ObrasAPI(InventarioCRUD):
    queryset = Obra.objects.all()
    serializer_class = ObraSerializer


class BodegasAPI(InventarioCRUD):
    queryset = Bodega.objects.all()
    serializer_class = BodegaSerializer


class HerramientasAPI(InventarioCRUD):
    queryset = Activo.objects.all()
    serializer_class = HerramientaSerializer


class MantenimientosAPI(InventarioCRUD):
    queryset = Mantenimiento.objects.all()
    serializer_class = MantenimientoSerializer

    def get_object(self):
        if self.action in ("update", "partial_update", "destroy"):
            # Usa el mismo orden de bloqueo que los flujos de mantenimiento existentes.
            pk = self.kwargs["pk"]
            if not pk.isascii() or not pk.isdecimal() or len(pk) > 19 or int(pk) > 2**63 - 1:
                raise Http404
            activo = self.queryset.filter(pk=pk).values("activo_id")
            if not Activo.objects.select_for_update().filter(pk__in=activo).first():
                raise Http404
        return super().get_object()

    def perform_destroy(self, instance):
        if instance.estado != Mantenimiento.Estado.PROGRAMADO:
            raise Conflicto("Solo se pueden eliminar mantenimientos programados.")
        instance.delete()


class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contratista
        fields = ("id", "nombre", "identificador", "contacto", "telefono", "direccion", "comuna", "region", "bloqueado_manual")
        read_only_fields = ("bloqueado_manual",)


class ClientesAPI(InventarioCRUD):
    queryset = Contratista.objects.all()
    serializer_class = ClienteSerializer


class PrestamoSerializer(serializers.ModelSerializer):
    estado_visible = serializers.CharField(read_only=True)
    bodega = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Prestamo
        fields = (
            "id", "activo", "contratista", "bodega", "entregado_en", "vence_en",
            "responsable_entrega", "firma_entrega", "devuelto_en",
            "responsable_devolucion", "horas_utilizadas", "estado_visible",
        )
        read_only_fields = ("entregado_en", "devuelto_en", "responsable_devolucion", "horas_utilizadas")

    def create(self, validated_data):
        usuario = self.context["request"].user
        try:
            return entregar(
                activo=validated_data["activo"],
                contratista=validated_data["contratista"],
                vence_en=validated_data["vence_en"],
                responsable=validated_data["responsable_entrega"],
                firma=validated_data["firma_entrega"],
                usuario=usuario,
            )
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from error


class DevolucionSerializer(serializers.Serializer):
    horas_utilizadas = serializers.IntegerField(min_value=0, max_value=100_000)
    responsable_devolucion = serializers.CharField(max_length=120)
    firma_devolucion = serializers.CharField(max_length=500)


class PrestamosAPI(viewsets.GenericViewSet, viewsets.mixins.ListModelMixin, viewsets.mixins.RetrieveModelMixin, viewsets.mixins.CreateModelMixin):
    authentication_classes = [JWTAuthentication]
    permission_classes = [PermisosInventario]
    queryset = Prestamo.objects.select_related("activo", "contratista", "bodega").all()
    serializer_class = PrestamoSerializer

    @action(detail=True, methods=["post"])
    def devolver(self, request, pk=None):
        prestamo = self.get_object()
        ser = DevolucionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            devolver(
                prestamo=prestamo,
                horas=ser.validated_data["horas_utilizadas"],
                responsable=ser.validated_data["responsable_devolucion"],
                firma=ser.validated_data["firma_devolucion"],
                usuario=request.user,
            )
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from error
        prestamo.refresh_from_db()
        return Response(self.get_serializer(prestamo).data)


class TrasladoSerializer(serializers.ModelSerializer):
    origen = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Traslado
        fields = ("id", "activo", "origen", "destino", "registrado_en")
        read_only_fields = ("registrado_en",)

    def create(self, validated_data):
        usuario = self.context["request"].user
        try:
            trasladar(activo=validated_data["activo"], destino=validated_data["destino"], usuario=usuario)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from error
        return Traslado.objects.filter(activo=validated_data["activo"]).first()


class TrasladosAPI(viewsets.GenericViewSet, viewsets.mixins.ListModelMixin, viewsets.mixins.RetrieveModelMixin, viewsets.mixins.CreateModelMixin):
    authentication_classes = [JWTAuthentication]
    permission_classes = [PermisosInventario]
    queryset = Traslado.objects.select_related("activo", "origen", "destino").all()
    serializer_class = TrasladoSerializer


@api_view(["GET"])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def salud(request):
    return Response({"estado": "ok"})


@api_view(["GET"])
@authentication_classes([JWTAuthentication])
@permission_classes([PermisosInventario])
def perfil(request):
    return Response({"usuario": request.user.get_username(), "puede_editar": puede_supervisar(request.user)})


@api_view(["GET"])
@authentication_classes([JWTAuthentication])
@permission_classes([PermisosInventario])
def guia(request):
    if not settings.RECURSOS_BUCKET:
        return Response({"detail": "El recurso S3 aún no está configurado."}, status=503)
    try:
        cliente = boto3.client("s3", region_name=settings.RECURSOS_REGION, config=Config(signature_version="s3v4"))
        url = cliente.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.RECURSOS_BUCKET, "Key": "recursos/guia-inventario.txt"},
            ExpiresIn=120,
        )
    except (BotoCoreError, ClientError):
        logger.exception("No se pudo firmar el recurso de inventario.")
        return Response({"detail": "Recurso temporalmente no disponible."}, status=503)
    return Response({"url": url, "vence_en_segundos": 120}, headers={"Cache-Control": "no-store"})


router = routers.SimpleRouter()
router.register("obras", ObrasAPI)
router.register("bodegas", BodegasAPI)
router.register("herramientas", HerramientasAPI)
router.register("mantenimientos", MantenimientosAPI)
router.register("clientes", ClientesAPI)
router.register("prestamos", PrestamosAPI)
router.register("traslados", TrasladosAPI)

urlpatterns = [
    path("salud/", salud),
    path("token/", TokenObtainPairView.as_view()),
    path("token/refresh/", TokenRefreshView.as_view()),
    path("perfil/", perfil),
    path("recursos/guia/", guia),
    path("", include(router.urls)),
]
