"""Django settings for the ClickUp clone backend.

Environment comes from backend/.env via django-environ; see .env.example.
"""

import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    # No usable default on purpose: a shipped fallback key would let anyone
    # mint valid JWTs against a production deployment that forgot to set it.
    SECRET_KEY=(str, ""),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    DATABASE_URL=(str, f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
    REDIS_URL=(str, ""),
    CORS_ALLOWED_ORIGINS=(list, ["http://localhost:3000"]),
    CSRF_TRUSTED_ORIGINS=(list, []),
    ACCESS_TOKEN_LIFETIME_MINUTES=(int, 60),
    REFRESH_TOKEN_LIFETIME_DAYS=(int, 7),
    INVITATION_TTL_DAYS=(int, 7),
    # Throttle rates (DRF "<n>/<period>"). Tightened defaults; see .env.example.
    AUTH_THROTTLE_RATE=(str, "10/min"),
    AUTH_BURST_THROTTLE_RATE=(str, "5/min"),
    REGISTER_THROTTLE_RATE=(str, "5/hour"),
    PASSWORD_CHANGE_THROTTLE_RATE=(str, "5/hour"),
    INVITE_THROTTLE_RATE=(str, "20/hour"),
    INVITE_LOOKUP_THROTTLE_RATE=(str, "30/hour"),
    AVATAR_THROTTLE_RATE=(str, "10/hour"),
    ATTACHMENT_THROTTLE_RATE=(str, "30/hour"),
    COMMENT_THROTTLE_RATE=(str, "60/min"),
    # WS handshake chiptasi (§15.1). Har qayta ulanish bitta chipta yoqadi, va
    # backoff 1s->30s bo'lgani uchun 60/min sog'lom klient uchun keng, chipta
    # zaxirasini yig'moqchi bo'lgan hisob uchun esa tor.
    REALTIME_TICKET_THROTTLE_RATE=(str, "60/min"),
    # Vazifa biriktirmasining maksimal hajmi (MB) — §10.7.
    MAX_ATTACHMENT_MB=(int, 10),
    DEMO_THROTTLE_RATE=(str, "10/hour"),
    # "Demo rejimda kirish" tugmasi. Prod'da o'chiq bo'lishi shart: yoqilganda
    # istalgan odam parolsiz demo hisobga kira oladi.
    DEMO_MODE=(bool, False),
    DEMO_USER_EMAIL=(str, "mehmon@clickish.dev"),
)
environ.Env.read_env(BASE_DIR / ".env")

DEBUG = env("DEBUG")


# --------------------------------------------------------------------------
# Secrets
# --------------------------------------------------------------------------

# Values that must never sign tokens outside of local development.
_WEAK_SECRETS = {
    "",
    "changeme",
    "change-me",
    "secret",
    "dev-only-change-me",
    "django-insecure",
}
_MIN_SECRET_LENGTH = 50

SECRET_KEY = env("SECRET_KEY").strip()

if not DEBUG:
    _normalised = SECRET_KEY.lower()
    if (
        _normalised in _WEAK_SECRETS
        or _normalised.startswith(("dev-", "django-insecure-", "test-"))
        or len(SECRET_KEY) < _MIN_SECRET_LENGTH
    ):
        raise ImproperlyConfigured(
            "SECRET_KEY is missing, weak or a development placeholder. Set a random "
            f"value of at least {_MIN_SECRET_LENGTH} characters in the environment, e.g. "
            "python -c \"import secrets; print(secrets.token_urlsafe(64))\""
        )
elif not SECRET_KEY:
    # Dev convenience only: never reached when DEBUG is off (checked above).
    # Ephemeral — every reload invalidates previously issued tokens, so set
    # SECRET_KEY in backend/.env for a stable local session.
    SECRET_KEY = secrets.token_urlsafe(64)

ALLOWED_HOSTS = env("ALLOWED_HOSTS")

if not DEBUG:
    if not ALLOWED_HOSTS:
        raise ImproperlyConfigured("ALLOWED_HOSTS must be set when DEBUG is off.")
    if "*" in ALLOWED_HOSTS:
        raise ImproperlyConfigured(
            "ALLOWED_HOSTS must not contain '*' when DEBUG is off; list the real hosts."
        )


# Application definition

DJANGO_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "channels",
]

LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.workspaces",
    "apps.tasks",
    "apps.comments",
    "apps.realtime",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# Database — sqlite in dev, postgres in prod, both via DATABASE_URL

DATABASES = {"default": env.db_url("DATABASE_URL")}


# Channels — falls back to the in-memory layer when REDIS_URL is unset (dev)

REDIS_URL = env("REDIS_URL")
if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }
else:
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}


# Cache — throttling counters live here, so a shared backend is required as
# soon as more than one worker process serves traffic.

if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "KEY_PREFIX": "clickup",
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "clickup-dev",
        }
    }


AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
        # Faqat o'qish hisoblari uchun fail-closed yozish qulfi. Ruxsat
        # matritsasi bu yo'llarning hammasini qamramaydi — izohni
        # `apps/core/drf_permissions.py` da o'qing.
        "apps.core.drf_permissions.BlockReadonlyAccountWrites",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "config.pagination.StandardPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "config.exceptions.api_exception_handler",
    # How many *trusted* proxies sit in front of the app.
    #
    # DRF's get_ident() takes addrs[-min(num_proxies, len(addrs))] from
    # X-Forwarded-For. With NUM_PROXIES=1 and NOTHING actually proxying us,
    # the header the client sent is the only entry, so it IS the throttle
    # identity: `X-Forwarded-For: <random>` on every request gives every
    # request its own bucket and defeats `auth`, `register`, `demo`,
    # `invite_lookup` and `avatar` alike. The default is therefore 0
    # (REMOTE_ADDR only, header ignored); a real proxy is an explicit opt-in
    # and the number must equal the count of proxies you control.
    "NUM_PROXIES": env.int("NUM_PROXIES", default=0),
    "DEFAULT_THROTTLE_RATES": {
        "auth": env("AUTH_THROTTLE_RATE"),
        "auth_burst": env("AUTH_BURST_THROTTLE_RATE"),
        "register": env("REGISTER_THROTTLE_RATE"),
        "password_change": env("PASSWORD_CHANGE_THROTTLE_RATE"),
        "invite": env("INVITE_THROTTLE_RATE"),
        "invite_lookup": env("INVITE_LOOKUP_THROTTLE_RATE"),
        "avatar": env("AVATAR_THROTTLE_RATE"),
        "attachment": env("ATTACHMENT_THROTTLE_RATE"),
        "comments": env("COMMENT_THROTTLE_RATE"),
        "realtime_ticket": env("REALTIME_TICKET_THROTTLE_RATE"),
        "demo": env("DEMO_THROTTLE_RATE"),
    },
}

# Demo rejim — `POST auth/demo/` parolsiz token beradi. O'chiq bo'lsa endpoint
# 404 qaytaradi (403 emas: mavjudligini oshkor qilmaydi).
DEMO_MODE = env("DEMO_MODE")
DEMO_USER_EMAIL = env("DEMO_USER_EMAIL")

# Invitations expire created_at + INVITATION_TTL_DAYS (docs/API_CONTRACT.md section 5)
INVITATION_TTL_DAYS = env("INVITATION_TTL_DAYS")

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env("ACCESS_TOKEN_LIFETIME_MINUTES")),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env("REFRESH_TOKEN_LIFETIME_DAYS")),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    # Defaults to SECRET_KEY, but can be rotated independently of session/CSRF
    # signing (rotating SECRET_KEY alone would invalidate every issued token).
    "SIGNING_KEY": env("JWT_SIGNING_KEY", default=SECRET_KEY),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "ClickUp Clone API",
    "DESCRIPTION": "REST API for the ClickUp clone. See docs/API_CONTRACT.md.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/api/v1",
    # The schema maps the whole attack surface; staff only.
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAdminUser"],
}

# Routes are only registered when this is on (see config/urls.py).
EXPOSE_API_DOCS = env.bool("EXPOSE_API_DOCS", default=False)

# Moving the admin off /admin/ stops the bulk of credential-stuffing noise.
ADMIN_URL = env("ADMIN_URL", default="admin/")

CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True

# Extra WebSocket origins beyond ALLOWED_HOSTS (the SPA is usually served from
# a different host than the API). Empty -> ALLOWED_HOSTS only. See config/asgi.py.
WS_ALLOWED_ORIGINS = env.list("WS_ALLOWED_ORIGINS", default=[])

# The frontend sends X-Client-Id on mutations so realtime consumers can
# suppress echoing the actor's own events back to it (API_CONTRACT §15).
from corsheaders.defaults import default_headers  # noqa: E402

CORS_ALLOW_HEADERS = [*default_headers, "x-client-id"]


# --------------------------------------------------------------------------
# Security headers / cookies
# --------------------------------------------------------------------------

X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")

if not DEBUG:
    # Terminating TLS at a proxy: trust its scheme header (only safe because
    # NUM_PROXIES above documents that a proxy really is in front of us).
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_AGE = env.int("SESSION_COOKIE_AGE", default=60 * 60 * 12)  # 12 h


# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------

# Only allow-listed LogRecord extras are serialised: django.request attaches the
# live HttpRequest to the record and that must never reach the log sink.
_LOG_RECORD_EXTRAS = ("request_id", "status_code", "method", "path", "user_id")


class _JsonFormatter(logging.Formatter):
    """One JSON object per line, so log shippers do not have to guess."""

    def format(self, record):
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for attr in _LOG_RECORD_EXTRAS:
            value = getattr(record, attr, None)
            if value is not None:
                payload[attr] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


LOG_LEVEL = env("LOG_LEVEL", default="DEBUG" if DEBUG else "INFO").upper()
LOG_FORMAT = env("LOG_FORMAT", default="console" if DEBUG else "json").lower()

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": _JsonFormatter},
        "console": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json" if LOG_FORMAT == "json" else "console",
        },
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        # 5xx and unhandled exceptions.
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        # Host-header attacks, suspicious operations, CSRF failures.
        "django.security": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.security.DisallowedHost": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        # Very chatty at DEBUG; keep SQL and event-loop internals out.
        "django.db.backends": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "asyncio": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "daphne": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "config": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "apps": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}


# --------------------------------------------------------------------------
# Error tracking (Sentry) — opt-in, absent DSN means "not wired at all"
# --------------------------------------------------------------------------

# Empty DSN: no import, no client, no network, no cost. That is the default,
# so local development and CI stay exactly as they were.
SENTRY_DSN = env("SENTRY_DSN", default="").strip()
SENTRY_ENVIRONMENT = env("SENTRY_ENVIRONMENT", default="development" if DEBUG else "production")
SENTRY_RELEASE = env("SENTRY_RELEASE", default="") or None
# Performance tracing is sampled separately from errors; 0.0 = errors only.
SENTRY_TRACES_SAMPLE_RATE = env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.0)

if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
    except ImportError:  # pragma: no cover - depends on requirements.txt
        # `sentry-sdk` is not a hard dependency of this project: a deployment
        # that sets a DSN without installing the package must still boot.
        logging.getLogger("config").warning(
            "SENTRY_DSN is set but sentry-sdk is not installed; error tracking is off. "
            "Add `sentry-sdk` to backend/requirements.txt to enable it."
        )
    else:
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            environment=SENTRY_ENVIRONMENT,
            release=SENTRY_RELEASE,
            integrations=[
                DjangoIntegration(),
                # Reuse the logging tree above instead of replacing it: INFO+
                # records become breadcrumbs, ERROR+ records become issues.
                # config/exceptions.py already logs every unhandled exception
                # with `request_id`, so the Sentry issue and the JSON log line
                # can be correlated from either side.
                LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
            ],
            traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
            # No emails, no auth headers, no request bodies, no cookies, no
            # client IPs. This API's payloads are user content by definition;
            # an error tracker is not a place to mirror them.
            send_default_pii=False,
            max_request_body_size="never",
        )


# Internationalization

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# Static & media

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# --------------------------------------------------------------------------
# Uploads (task attachments — docs/API_CONTRACT.md §10.7)
# --------------------------------------------------------------------------

#: Bitta biriktirmaning maksimal hajmi. View qatlami `upload.size` ni shu
#: chegaraga solishtiradi va oshib ketsa `400 validation_error` qaytaradi.
MAX_ATTACHMENT_MB = env("MAX_ATTACHMENT_MB")
MAX_ATTACHMENT_BYTES = MAX_ATTACHMENT_MB * 1024 * 1024

#: Multipart so'rovning **fayl bo'lmagan** qismi uchun chegara (Django
#: defaulti bilan bir xil). Fayllar bu chegaraga kirmaydi — ular
#: `FILE_UPLOAD_MAX_MEMORY_SIZE` dan katta bo'lsa diskka oqiziladi.
DATA_UPLOAD_MAX_MEMORY_SIZE = env.int("DATA_UPLOAD_MAX_MEMORY_SIZE", default=2621440)

#: Bundan katta fayl xotirada emas, vaqtinchalik faylda yig'iladi — 10 MB lik
#: yuklama RAM'ni band qilmasligi uchun ataylab past (2.5 MB).
FILE_UPLOAD_MAX_MEMORY_SIZE = env.int("FILE_UPLOAD_MAX_MEMORY_SIZE", default=2621440)

#: Bitta so'rovdagi fayllar soni — "million bo'sh fayl" DoS'iga qarshi.
DATA_UPLOAD_MAX_NUMBER_FILES = env.int("DATA_UPLOAD_MAX_NUMBER_FILES", default=10)

#: Yuklangan fayl diskda 0o644 bo'lsin (ba'zi tizimlarda default 0o600 bo'lib,
#: web-server o'qiy olmaydi). Hech qachon bajariladigan bit qo'yilmaydi.
FILE_UPLOAD_PERMISSIONS = 0o644

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
