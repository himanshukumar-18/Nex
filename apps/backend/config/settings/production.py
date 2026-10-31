"""
NEX Backend — production settings.

All required production variables are validated at startup.
The application will refuse to start if mandatory settings are missing
or if insecure defaults are detected.

Required environment variables:
  DJANGO_SECRET_KEY          -- random 50+ character secret key
  DATABASE_URL               -- postgres://user:pass@host:port/dbname
  DJANGO_ALLOWED_HOSTS       -- comma-separated list of public hostnames

Optional:
  REDIS_URL                  -- redis://:pass@host:port/0

──────────────────────────────────────────────────────────────────────────────
HTTPS enforcement design
──────────────────────────────────────────────────────────────────────────────
Django does NOT perform HTTP → HTTPS redirects itself (SECURE_SSL_REDIRECT is
intentionally False). The redirect is the responsibility of the upstream proxy:

  Production topology:
    Internet → TLS-terminating LB (port 443) → Nginx (port 80) → Django

  The LB or Nginx should:
    1. Redirect HTTP (port 80) requests to HTTPS (port 443).
    2. Set X-Forwarded-Proto: https on every request forwarded to Django.

  Django uses SECURE_PROXY_SSL_HEADER to learn that the connection arrived
  via HTTPS. It then enforces secure cookies, HSTS, and CSRF correctly,
  without needing to redirect itself.

  This avoids the redirect loop that occurs when SECURE_SSL_REDIRECT=True
  and Nginx sets X-Forwarded-Proto: http (its own connection to Django is HTTP).

  Security guarantee: Django is only reachable from Nginx via the internal
  Docker network. No request can reach Django without passing through Nginx
  first, so the X-Forwarded-Proto header comes only from a trusted source.

See infrastructure/nginx/README.md for the TLS deployment checklist.
"""

import sys

from .base import *  # noqa: F401, F403
from .base import env

# ---------------------------------------------------------------------------
# Security — strict production settings
# ---------------------------------------------------------------------------

DEBUG = False

_raw_hosts = env("DJANGO_ALLOWED_HOSTS", default="")
if not _raw_hosts:
    print(  # noqa: T201
        "FATAL: DJANGO_ALLOWED_HOSTS is not set. "
        "The production application cannot start without it.",
        file=sys.stderr,
    )
    sys.exit(1)

ALLOWED_HOSTS = [h.strip() for h in _raw_hosts.split(",") if h.strip()]

# ---------------------------------------------------------------------------
# HTTPS / proxy configuration
#
# SECURE_SSL_REDIRECT is False — HTTP→HTTPS redirect is handled by the upstream
# load balancer or Nginx, not by Django. Performing the redirect here would
# create an infinite loop because Nginx always connects to Django via HTTP on
# the internal network.
#
# SECURE_PROXY_SSL_HEADER tells Django that when the upstream proxy sets
# X-Forwarded-Proto: https, the original client connection was HTTPS.
# Django uses this to enforce secure cookies and add HSTS headers.
#
# Trust assumption: Django is only reachable via Nginx on the internal Docker
# network (internal: true). Nginx is configured to set X-Forwarded-Proto: https
# only when the upstream connection (from the TLS LB to Nginx) arrives via
# HTTPS. No external client can forge this header.
# ---------------------------------------------------------------------------

SECURE_SSL_REDIRECT = False  # Redirect handled at Nginx / LB layer — see docstring
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Secure cookie and session settings — effective once HTTPS is active end-to-end
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# HSTS — tell browsers to always use HTTPS for this domain.
# Only effective when HTTPS is actually configured end-to-end.
# Do not set SECURE_HSTS_PRELOAD until the domain is confirmed stable and
# HSTS behaviour is fully understood; preloading is difficult to undo.
SECURE_HSTS_SECONDS = 31536000          # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# ---------------------------------------------------------------------------
# Validate critical secrets — refuse to start with insecure defaults
# ---------------------------------------------------------------------------

from .base import SECRET_KEY as _secret_key  # noqa: E402

_insecure_defaults = {"change-me", "changeme", "secret", "django-insecure", "nex-rate-limit-dev-change-me"}
if not _secret_key or _secret_key.lower() in _insecure_defaults or len(_secret_key) < 50:
    print(  # noqa: T201
        "FATAL: DJANGO_SECRET_KEY is missing or insecure. "
        "Provide a random 50+ character value in the production environment.",
        file=sys.stderr,
    )
    sys.exit(1)

_rate_limit_secret = env("RATE_LIMIT_HMAC_SECRET", default="")
if not _rate_limit_secret or _rate_limit_secret.lower() in _insecure_defaults or len(_rate_limit_secret) < 32:
    print(  # noqa: T201
        "FATAL: RATE_LIMIT_HMAC_SECRET is missing or insecure in production. "
        "Provide a dedicated 32+ character random secret.",
        file=sys.stderr,
    )
    sys.exit(1)

# Inter-service authentication secret validation
_internal_service_secret = env("INTERNAL_SERVICE_SECRET", default="")
if not _internal_service_secret or _internal_service_secret.lower() in _insecure_defaults or len(_internal_service_secret) < 32:
    print(  # noqa: T201
        "FATAL: INTERNAL_SERVICE_SECRET is missing or insecure in production. "
        "Provide a dedicated 32+ character random secret for inter-service communication.",
        file=sys.stderr,
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Database — must be set explicitly; no fallback in production
# ---------------------------------------------------------------------------

_prod_db = env.db("DATABASE_URL", default=None)
if not _prod_db:
    print(  # noqa: T201
        "FATAL: DATABASE_URL is not set. "
        "The production application cannot start without it.",
        file=sys.stderr,
    )
    sys.exit(1)

# Preserve base connection pooling, health checks, and query timeout options
_db_options = DATABASES["default"].get("OPTIONS", {})
DATABASES["default"] = _prod_db
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = env.bool("DB_CONN_HEALTH_CHECKS", default=True)
DATABASES["default"]["OPTIONS"] = _db_options

# Verify credentials consistency if POSTGRES_PASSWORD is also defined
_pg_password = env("POSTGRES_PASSWORD", default="")
if _pg_password and DATABASES["default"].get("PASSWORD"):
    if DATABASES["default"]["PASSWORD"] != _pg_password and DATABASES["default"].get("HOST") in ("postgres", "127.0.0.1", "localhost"):
        print(  # noqa: T201
            "FATAL: DATABASE_URL password and POSTGRES_PASSWORD disagree. "
            "Ensure database credentials are consistent across environment settings.",
            file=sys.stderr,
        )
        sys.exit(1)
