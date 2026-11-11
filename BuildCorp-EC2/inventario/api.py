from rest_framework import permissions, routers, serializers, viewsets

from .access import puede_operar
from .models import Activo, Mantenimiento, Prestamo, Traslado


class AccesoInventario(permissions.BasePermission):
    def has_permission(self, request, view):
        return puede_operar(request.user)


class ActivoSerializer(serializers.ModelSerializer):
    estado = serializers.CharField(read_only=True)
    bodega = serializers.StringRelatedField()

    class Meta:
        model = Activo
        fields = ("id", "codigo", "nombre", "descripcion", "bodega", "horas_uso", "estado")


class PrestamoSerializer(serializers.ModelSerializer):
    vencido = serializers.BooleanField(read_only=True)

    class Meta:
        model = Prestamo
        fields = (
            "id", "activo", "contratista", "bodega", "entregado_en", "vence_en",
            "devuelto_en", "horas_utilizadas", "vencido",
        )


class MantenimientoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mantenimiento
        fields = ("id", "activo", "tarea", "fecha_limite", "horas_limite", "estado", "iniciado_en", "cerrado_en")


class TrasladoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Traslado
        fields = ("id", "activo", "origen", "destino", "registrado_en")


class Consulta(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AccesoInventario]


class ActivoAPI(Consulta):
    serializer_class = ActivoSerializer
    queryset = Activo.objects.select_related("bodega__obra")


class PrestamoAPI(Consulta):
    serializer_class = PrestamoSerializer
    queryset = Prestamo.objects.all()


class MantenimientoAPI(Consulta):
    serializer_class = MantenimientoSerializer
    queryset = Mantenimiento.objects.all()


class TrasladoAPI(Consulta):
    serializer_class = TrasladoSerializer
    queryset = Traslado.objects.all()


router = routers.SimpleRouter()
router.register("herramientas", ActivoAPI)
router.register("prestamos", PrestamoAPI)
router.register("mantenimientos", MantenimientoAPI)
router.register("traslados", TrasladoAPI)
