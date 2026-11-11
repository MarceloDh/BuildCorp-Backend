from django.contrib import admin
from django.contrib.admin import SimpleListFilter

from .models import Activo, Bodega, Contratista, Mantenimiento, Obra, Prestamo, Servicio, SolicitudServicio, Traslado

admin.site.site_header = "BuildCorp · Gestión"
admin.site.site_title = "Gestión BuildCorp"
admin.site.index_title = "Registros de BuildCorp"


@admin.register(Obra)
class ObraAdmin(admin.ModelAdmin):
    list_display = ("nombre", "direccion")
    search_fields = ("nombre", "direccion")


@admin.register(Bodega)
class BodegaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "obra")
    list_filter = ("obra",)
    search_fields = ("nombre", "obra__nombre")

    def get_readonly_fields(self, request, obj=None):
        return ("obra",) if obj else ()


@admin.register(Contratista)
class ContratistaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "identificador", "contacto", "cuenta", "bloqueado_manual", "tiene_atrasos")
    list_filter = ("bloqueado_manual",)
    list_select_related = ("cuenta",)
    search_fields = ("nombre", "identificador", "cuenta__username")
    autocomplete_fields = ("cuenta",)

    @admin.display(description="Tiene atrasos", boolean=True)
    def tiene_atrasos(self, contratista):
        return contratista.prestamos.vencidos().exists()


class DisponibilidadFilter(SimpleListFilter):
    title = "estado de la herramienta"
    parameter_name = "estado"

    def lookups(self, request, model_admin):
        return Activo.Estado.choices

    def queryset(self, request, queryset):
        estado = self.value()
        if estado == Activo.Estado.BAJA:
            return queryset.filter(dado_de_baja=True)
        if estado == Activo.Estado.EN_USO:
            return queryset.filter(dado_de_baja=False, pk__in=Prestamo.objects.abiertos().values("activo"))
        if estado == Activo.Estado.RESERVADO:
            return queryset.filter(pk__in=SolicitudServicio.objects.filter(
                estado="pendiente", pago_aprobado=True, activo__isnull=False,
            ).values("activo"))
        en_mantenimiento = Mantenimiento.objects.filter(estado=Mantenimiento.Estado.EN_CURSO).values("activo")
        if estado == Activo.Estado.MANTENIMIENTO:
            return queryset.filter(dado_de_baja=False, pk__in=en_mantenimiento)
        if estado == Activo.Estado.DISPONIBLE:
            return queryset.filter(dado_de_baja=False).exclude(
                pk__in=Prestamo.objects.abiertos().values("activo"),
            ).exclude(pk__in=en_mantenimiento).exclude(pk__in=SolicitudServicio.objects.filter(
                estado="pendiente", pago_aprobado=True, activo__isnull=False,
            ).values("activo"))
        return queryset


@admin.register(Activo)
class ActivoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "bodega", "estado_visible", "horas_uso")
    list_filter = ("bodega__obra", "bodega", DisponibilidadFilter, "mostrar_en_catalogo")
    list_select_related = ("bodega__obra",)
    search_fields = ("codigo", "nombre")

    def get_readonly_fields(self, request, obj=None):
        return ("bodega", "dado_de_baja", "horas_uso", "servicio") if obj else ("dado_de_baja",)

    def save_model(self, request, obj, form, change):
        if change:
            obj.save(update_fields=["codigo", "nombre", "descripcion", "mostrar_en_catalogo"])
        else:
            super().save_model(request, obj, form, change)


class HistorialAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria", "tarifa", "publicado", "disponibles")
    list_filter = ("categoria", "publicado")
    search_fields = ("nombre", "codigo")


@admin.register(SolicitudServicio)
class SolicitudServicioAdmin(HistorialAdmin):
    list_display = ("servicio", "contratista", "fecha", "comuna", "total", "pago_aprobado")
    list_filter = ("pago_aprobado", "fecha", "region")
    search_fields = ("nombre", "apellido", "correo", "servicio", "contratista__nombre")
    list_select_related = ("contratista",)


@admin.register(Prestamo)
class PrestamoAdmin(HistorialAdmin):
    exclude = ("firma_entrega", "firma_devolucion")
    list_display = ("activo", "contratista", "vence_en", "devuelto_en", "estado_visible")
    list_filter = ("bodega__obra", "devuelto_en")
    search_fields = ("activo__codigo", "activo__nombre", "contratista__nombre", "contratista__identificador")


@admin.register(Mantenimiento)
class MantenimientoAdmin(HistorialAdmin):
    list_display = ("activo", "tarea", "estado", "fecha_limite", "horas_limite")
    list_filter = ("estado", "activo__bodega__obra")
    search_fields = ("activo__codigo", "tarea")


@admin.register(Traslado)
class TrasladoAdmin(HistorialAdmin):
    list_display = ("activo", "origen", "destino", "registrado_en")
    list_filter = ("origen__obra", "destino__obra")
    search_fields = ("activo__codigo", "origen__nombre", "destino__nombre")
