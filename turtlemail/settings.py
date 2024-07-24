"""
Django settings for turtlemail project.

Generated by 'django-admin startproject' using Django 4.2.11.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.2/ref/settings/
"""

from datetime import timedelta
from pathlib import Path
import sys

from dotenv import load_dotenv
import dj_database_url
from django_jinja.builtins import DEFAULT_EXTENSIONS
from django.utils.translation import gettext_lazy as _

from turtlemail import __version__
from turtlemail.base.env import get_env, get_env_list, is_env_true, parse_channel_layers

BASE_DIR = Path(__file__).resolve().parent.parent

# load custom env
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / ".env.local")

DATA_DIR = get_env("DATA_DIR", cast=Path, default=BASE_DIR / "data")
DATA_DIR.mkdir(exist_ok=True)


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = get_env("SECRET_KEY", default=None)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = is_env_true("DEBUG")

ALLOWED_HOSTS = get_env_list("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = get_env_list(
    "CSRF_TRUSTED_ORIGINS",
    default=[f"https://{host}" for host in ALLOWED_HOSTS],
)

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    "django.contrib.sites",
    "django.contrib.flatpages",
    "django_jinja",
    "huey.contrib.djhuey",
    "turtlemail.apps.TurtlemailConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.contrib.flatpages.middleware.FlatpageFallbackMiddleware",
]

ROOT_URLCONF = "turtlemail.urls"

TEMPLATES = [
    {
        "NAME": "jinja",
        "BACKEND": "django_jinja.backend.Jinja2",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "extensions": [
                *DEFAULT_EXTENSIONS,
            ],
            "auto_reload": DEBUG,
            "context_processors": [
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "turtlemail.wsgi.application"

SESSION_COOKIE_AGE = get_env("SESSION_TIMEOUT_SECONDS", cast=int, default=1209600)


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    "default": dj_database_url.config(
        "DATABASE_URL",
        f"sqlite:///{DATA_DIR / 'db.sqlite'}",
        engine="django.contrib.gis.db.backends.postgis",
    )
}


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# sites framework
SITE_ID = 1

# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = "de-de"
LANGUAGES = [("de", _("German"))]
TIME_ZONE = "Europe/Berlin"
USE_I18N = True
USE_TZ = True

MEDIA_ROOT = DATA_DIR / "public" / "media"
MEDIA_URL = "/-/media/"

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STORAGES = {"staticfiles": {"BACKEND": "turtlemail.base.storage.ManifestStorage"}}
STATIC_ROOT = DATA_DIR / "public" / "static"
STATIC_URL = "/-/static/"

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

USE_X_FORWARDED_HOST = True

# Email Settings
# see: https://docs.djangoproject.com/en/4.2/topics/email/#smtp-backend
if smtp_url := get_env("EMAIL_SMTP", default=None):
    EMAIL_BACKEND = "turtlemail.base.mail.EmailBackend"
    EMAIL_BACKEND_URL = smtp_url
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = get_env("EMAIL_DEFAULT_FROM", default="noreply@turtlemail.app")
SUPPORT_EMAIL = get_env("SUPPORT_EMAIL", default="team@turtlemail.app")

ASSET_SOURCE = get_env("ASSET_SOURCE", default=None)
VITE_HOST = get_env("VITE_HOST", default="localhost")
VITE_PUBLIC_HOST = get_env("PUBLIC_VITE_HOST", default="localhost")
VITE_PORT = get_env("VITE_PORT", cast=int, default=8638)
VITE_MANIFEST = (
    BASE_DIR
    / "turtlemail"
    / "static"
    / "turtlemail"
    / "bundled"
    / ".vite"
    / "manifest.json"
)

# RELEASE might be set but empty, so we fall back to __version__
RELEASE = get_env("RELEASE", default="") or __version__
ENVIRONMENT = get_env("ENVIRONMENT", default="unknown")
SENTRY_DSN = get_env("SENTRY_DSN", default="")

# custom user model
AUTH_USER_MODEL = "turtlemail.User"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "index"
LOGOUT_REDIRECT_URL = "index"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "filters": {
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        },
    },
    # Show debug logs when DEBUG is True.
    # This is also intended to show logs in tests.
    # Unfortunately, they're mixed with the test runner's output
    # for now.
    "root": {
        "handlers": ["console"],
        "level": "DEBUG",
        "filters": ["require_debug_true"],
    },
}

TURTLEMAIL_MAX_ROUTE_LENGTH = timedelta(
    days=get_env(
        "TURTLEMAIL_MAX_ROUTE_LENGTH_DAYS",
        default=60,
        cast=float,
    )
)

# channels for websocket connections: chat, push notifications
CHANNEL_LAYERS = parse_channel_layers(
    "CHANNEL_LAYER_URL", default="memory://" if "test" in sys.argv else None
)
SQIDS_SALT = get_env("SQIDS_SALT", default=None)

_huey_redis_url = get_env("HUEY_REDIS_URL", default=DEBUG)
_huey_debug = is_env_true("HUEY_DEBUG", default=False)

# async tasks needed for background work like clean up or push features
HUEY = {
    "huey_class": "huey.RedisHuey",
    "name": "turtlemail",
    "immediate": _huey_debug,
    "immediate_use_memory": _huey_redis_url is None,
    "connection": {"url": _huey_redis_url},
    "consumer": {
        "workers": get_env("HUEY_WORKER_COUNT", cast=int, default=1),
        "worker_type": get_env("HUEY_WORKER_TYPE", default="thread"),
    },
}

# WARNING: don’t add configuration settings after this line
try:
    sys.path.insert(0, "/etc/turtlemail")
    from turtlemail_settings import *  # noqa: F401,F403
except ImportError:
    pass

if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        auto_session_tracking=False,
        release=RELEASE,
        environment=ENVIRONMENT,
        traces_sample_rate=0,
    )


ACTIVITY_LENGTH = 3
