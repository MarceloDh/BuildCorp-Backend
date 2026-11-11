from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView

from inventario.api import router
from inventario.views import AccesoBuildCorp
from . import errors

handler400 = errors.solicitud_invalida
handler403 = errors.acceso_restringido
handler404 = errors.pagina_no_encontrada
handler500 = errors.error_servidor

rutas = [
    path("acceso/", AccesoBuildCorp.as_view(), name="login"),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
    path(settings.ADMIN_PATH, admin.site.urls),
    path("api/", include(router.urls)),
    path("", include("inventario.urls")),
]
urlpatterns = [path(settings.APP_PREFIX, include(rutas))]
if settings.APP_PREFIX:
    urlpatterns += [path("", RedirectView.as_view(pattern_name="portada"))]
