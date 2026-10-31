"""
NEX Backend — base settings.

Shared configuration imported by all environment-specific settings modules.
Do not import this module directly; import development.py or production.py.
"""

from pathlib import Path

import environ

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# apps/backend/
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

env = environ.Env()

# ---------------------------------------------------------------------------
# Security — SECRET_KEY is always required from environment
# ---------------------------------------------------------------------------

SECRET_KEY = env("DJANGO_SECRET_KEY")

# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------

DJANGO_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
]

THIRD_PARTY_APPS = [
    "rest_framework",
]

LOCAL_APPS: list[str] = [
    "apps.core",
    "apps.api",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    # Correlation ID must be first so all downstream handlers can access it.
    "apps.api.middleware.CorrelationIdMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://nex:nex@postgres:5432/nex",
    )
}

# Connection management & reliability
# Persistent connections (60s default) to avoid per-request connection overhead.
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = env.bool("DB_CONN_HEALTH_CHECKS", default=True)

# Safe PostgreSQL connection options & timeouts
db_options = DATABASES["default"].get("OPTIONS", {})
db_options.setdefault("connect_timeout", env.int("DB_CONNECT_TIMEOUT", default=10))

# Safe session timeouts:
# - statement_timeout: limits query execution time to protect against runaway queries
# - lock_timeout: prevents transactions from waiting indefinitely on row/table locks
# - idle_in_transaction_session_timeout: drops orphaned transactions holding locks
statement_timeout_ms = env.int("DB_STATEMENT_TIMEOUT_MS", default=30000)
lock_timeout_ms = env.int("DB_LOCK_TIMEOUT_MS", default=10000)
idle_in_tx_timeout_ms = env.int("DB_IDLE_TRANSACTION_TIMEOUT_MS", default=60000)

db_options.setdefault(
    "options",
    f"-c statement_timeout={statement_timeout_ms} "
    f"-c lock_timeout={lock_timeout_ms} "
    f"-c idle_in_transaction_session_timeout={idle_in_tx_timeout_ms}",
)
DATABASES["default"]["OPTIONS"] = db_options

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Redis cache configuration
# ---------------------------------------------------------------------------
#
# Two named cache aliases:
#
#   "default"     — General-purpose Django cache (sessions, view cache).
#                   Use this for application-level caching.
#
#   "rate_limit"  — Dedicated cache for the distributed sliding-window rate
#                   limiter. Isolated to prevent cache stampedes in the default
#                   cache from affecting rate-limit atomicity.
#                   Key namespace: "rl:" to distinguish from other aliases.
#
# Both aliases connect to the same Redis instance in development.
# In production, point them at separate Redis databases or instances if needed.
#
# Connection pooling:
#   CONNECTION_POOL_KWARGS sets max_connections=20 per worker to prevent
#   connection exhaustion under high concurrency.
#
# Timeout:
#   SOCKET_CONNECT_TIMEOUT and SOCKET_TIMEOUT limit how long Django will wait
#   for Redis before failing.  Values match the PostgreSQL connect_timeout.
#
_REDIS_URL = env("REDIS_URL", default="redis://redis:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": _REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "CONNECTION_POOL_KWARGS": {"max_connections": 20},
            "IGNORE_EXCEPTIONS": True,  # Cache miss on Redis failure; does not affect rate limiter
        },
        "KEY_PREFIX": "nex",
    },
    "rate_limit": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": _REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "CONNECTION_POOL_KWARGS": {"max_connections": 20},
            # IGNORE_EXCEPTIONS is False for rate_limit: the throttle's own
            # fail-open/fail-closed policy handles Redis unavailability.
            "IGNORE_EXCEPTIONS": False,
        },
        "KEY_PREFIX": "rl",
    },
}

# ---------------------------------------------------------------------------
# Rate limiting configuration
# ---------------------------------------------------------------------------
#
# RATE_LIMIT_CACHE_ALIAS   — must match a key in CACHES above
# RATE_LIMIT_FAIL_OPEN     — True: allow requests when Redis is unreachable
#                            False: block requests when Redis is unreachable
# NUM_PROXIES              — Number of trusted upstream reverse proxies.
#                            0 = direct connection (trust REMOTE_ADDR only)
#                            1 = one proxy (Nginx in Docker Compose)
#                            Adjust when behind a load balancer or CDN.
# RATE_LIMIT_HMAC_SECRET   — Secret used to HMAC-mask client IDs in Redis keys.
#                            Override in production with a strong random value.
#

RATE_LIMIT_CACHE_ALIAS: str = "rate_limit"
RATE_LIMIT_FAIL_OPEN: bool = env.bool("RATE_LIMIT_FAIL_OPEN", default=True)
NUM_PROXIES: int = env.int("NUM_PROXIES", default=1)
RATE_LIMIT_HMAC_SECRET: str = env("RATE_LIMIT_HMAC_SECRET", default="nex-rate-limit-dev-change-me")

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ---------------------------------------------------------------------------
# Logging — stdout/stderr only; no file handlers; no sensitive data
# ---------------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        # Injects correlation_id into every log record during a request.
        # Records produced outside a request context (management commands)
        # receive correlation_id = "no-request".
        "add_correlation_id": {
            "()": "apps.api.middleware.CorrelationIdFilter",
        },
    },
    "formatters": {
        "json_line": {
            "format": (
                '{"time":"%(asctime)s","level":"%(levelname)s",'
                '"logger":"%(name)s","correlation_id":"%(correlation_id)s",'
                '"message":"%(message)s"}'
            ),
        },
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "json_line",
            "filters": ["add_correlation_id"],
        },
        "stderr": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
            "formatter": "json_line",
            "filters": ["add_correlation_id"],
        },
    },
    "root": {
        "handlers": ["stdout"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["stdout"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["stderr"],
            "level": "WARNING",
            "propagate": False,
        },
        "apps": {
            "handlers": ["stdout"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# ---------------------------------------------------------------------------
# Django REST Framework — production-grade base configuration
# ---------------------------------------------------------------------------
#
# Authentication and permission classes are intentionally left empty at the
# framework default for now. Step 5B (authentication) will configure:
#   DEFAULT_AUTHENTICATION_CLASSES with JWT/session authentication
#   DEFAULT_PERMISSION_CLASSES with IsAuthenticatedUser
#
# The exception handler, pagination, and renderer settings are set here
# because they are architecture-level, not authentication-level concerns.
#

REST_FRAMEWORK: dict = {
    # All responses are JSON-only; browser API is disabled for security.
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    # Centralized exception handler normalizes all errors into the NEX envelope.
    "EXCEPTION_HANDLER": "apps.api.exceptions.nex_exception_handler",
    # Default pagination for all list views; views can override with cursor pagination.
    "DEFAULT_PAGINATION_CLASS": "apps.api.pagination.NexPageNumberPagination",
    "PAGE_SIZE": 20,
    # Default throttle classes applied to all views.
    # Views must override this with policy-specific throttle classes.
    "DEFAULT_THROTTLE_CLASSES": [
        "apps.api.throttling.AnonymousRateThrottle",
        "apps.api.throttling.AuthenticatedRateThrottle",
    ],
    # Permission and authentication — configured in Step 5B.
    # Explicitly listed here as reminder anchors; do not remove.
    "DEFAULT_AUTHENTICATION_CLASSES": [],   # Step 5B: add JWT + session auth
    "DEFAULT_PERMISSION_CLASSES": [],       # Step 5B: add IsAuthenticatedUser
}

# ---------------------------------------------------------------------------
# Inter-Service Communication — FastAPI Agent Runtime
# ---------------------------------------------------------------------------

AGENT_RUNTIME_URL: str = env("AGENT_RUNTIME_URL", default="http://agent-runtime:8001")
INTERNAL_SERVICE_SECRET: str = env("INTERNAL_SERVICE_SECRET", default="")
INTERNAL_SERVICE_SECRET_FALLBACK: str = env("INTERNAL_SERVICE_SECRET_FALLBACK", default="")

# Bounded connection & request timeouts (seconds)
AGENT_RUNTIME_CONNECT_TIMEOUT: float = 3.0
AGENT_RUNTIME_READ_TIMEOUT: float = 15.0
AGENT_RUNTIME_WRITE_TIMEOUT: float = 10.0
AGENT_RUNTIME_POOL_TIMEOUT: float = 5.0


