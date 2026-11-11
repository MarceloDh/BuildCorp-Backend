from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string


def respuesta_error(request, codigo, titulo, mensaje):
    if request.path_info.startswith(f"/{settings.APP_PREFIX}api/"):
        return JsonResponse({"detail": titulo}, status=codigo)
    contenido = render_to_string("error.html", {
        "codigo": codigo, "titulo": titulo, "mensaje": mensaje,
    })
    return HttpResponse(contenido, status=codigo)


def pagina_no_encontrada(request, exception=None):
    return respuesta_error(
        request, 404, "Esta página no existe",
        "Puede que la dirección haya cambiado o que el enlace esté incompleto. "
        "Nuestro supervisor te acompaña de vuelta al inicio.",
    )


def acceso_restringido(request, exception=None):
    return respuesta_error(
        request, 403, "Acceso restringido",
        "Tu cuenta no tiene permiso para abrir esta sección. "
        "Puedes volver al inicio y continuar desde tu cuenta.",
    )


def solicitud_invalida(request, exception=None):
    return respuesta_error(
        request, 400, "No pudimos abrir esta solicitud",
        "Revisa la dirección o vuelve al inicio para continuar.",
    )


def error_servidor(request):
    return respuesta_error(
        request, 500, "Tenemos un problema en el taller",
        "No pudimos completar tu solicitud. Vuelve al inicio e inténtalo de nuevo en unos minutos.",
    )


def formulario_vencido(request, reason=""):
    return respuesta_error(
        request, 403, "Vuelve a abrir el formulario",
        "El formulario venció o no pudo verificarse. Abre la página de nuevo antes de enviarlo. "
        "Si estabas iniciando sesión, vuelve a Mi cuenta.",
    )


class ErroresPublicosMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # En desarrollo, el framework sustituye handler404 por su diagnóstico técnico.
        if (
            settings.DEBUG and response.status_code == 404
            and response.headers.get("Content-Type", "").startswith("text/html")
        ):
            return pagina_no_encontrada(request)
        return response
