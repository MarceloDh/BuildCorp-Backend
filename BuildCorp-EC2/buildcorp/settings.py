import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DEBUG = os.getenv("DEBUG", "0") == "1"
SECRET_KEY = os.getenv("SECRET_KEY") or ("solo-para-desarrollo" if DEBUG else "")
if not SECRET_KEY:
    raise ImproperlyConfigured("Configura SECRET_KEY en el entorno.")
ALLOWED_HOSTS = [
    host.strip() for host in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]
if not DEBUG and (not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS):
    raise ImproperlyConfigured("Configura la IP pública o el DNS en ALLOWED_HOSTS.")
CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]
ADMIN_PATH = os.getenv("ADMIN_PATH", "gestion").strip("/") + "/"
if ADMIN_PATH.split("/", 1)[0] in {
    "", "acceso", "salir", "api", "herramientas", "registros", "prestamos", "mantenimiento",
    "static", "bodega", "mi-cuenta", "catalogo", "registro",
}:
    raise ImproperlyConfigured("Configura una ruta de gestión distinta de las rutas de operación.")
APP_PREFIX = os.getenv("APP_PREFIX", "").strip("/")
if APP_PREFIX:
    APP_PREFIX += "/"
HTTPS = os.getenv("HTTPS", "0") == "1"

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "rest_framework", "inventario",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "buildcorp.errors.ErroresPublicosMiddleware",
]
ROOT_URLCONF = "buildcorp.urls"
WSGI_APPLICATION = "buildcorp.wsgi.application"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "inventario.access.nav_access",
    ]},
}]

db_engine = os.getenv("DB_ENGINE", "postgresql")
if db_engine == "sqlite" and DEBUG:
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3",
    }}
elif db_engine == "postgresql":
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "buildcorp"),
        "USER": os.getenv("DB_USER", "buildcorp"),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }}
else:
    raise ImproperlyConfigured("Configura PostgreSQL para producción.")

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": f"django.contrib.auth.password_validation.{validator}"}
    for validator in (
        "UserAttributeSimilarityValidator", "MinimumLengthValidator",
        "CommonPasswordValidator", "NumericPasswordValidator",
    )
]
LANGUAGE_CODE = "es-cl"
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "portada"
LOGOUT_REDIRECT_URL = "portada"

SESSION_COOKIE_SECURE = HTTPS
CSRF_COOKIE_SECURE = HTTPS
CSRF_FAILURE_VIEW = "buildcorp.errors.formulario_vencido"
SECURE_SSL_REDIRECT = HTTPS
if HTTPS:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = int(os.getenv("HSTS_SECONDS", "0"))

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
}
