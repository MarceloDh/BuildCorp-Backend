from django.core.exceptions import PermissionDenied

SUPERVISOR = "Supervisión"
OPERADOR = "Bodega"


def puede_supervisar(user):
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name=SUPERVISOR).exists()
    )


def puede_operar(user):
    return user.is_authenticated and (
        puede_supervisar(user) or user.groups.filter(name=OPERADOR).exists()
    )


def perfil_contratista(user):
    return getattr(user, "perfil_contratista", None) if user.is_authenticated else None


def nav_access(request):
    return {
        "puede_operar": puede_operar(request.user),
        "puede_supervisar": puede_supervisar(request.user),
        "es_contratista": perfil_contratista(request.user) is not None,
    }


def exigir_acceso(user, *, supervision=False):
    autorizado = puede_supervisar(user) if supervision else puede_operar(user)
    if not autorizado:
        raise PermissionDenied
