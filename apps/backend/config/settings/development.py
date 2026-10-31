"""
NEX Backend — development settings.

Overrides for local Docker development.
Never use these settings in production.
"""

from .base import *  # noqa: F401, F403
from .base import env

# ---------------------------------------------------------------------------
# Security — relaxed for local development only
# ---------------------------------------------------------------------------

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "backend"]

# ---------------------------------------------------------------------------
# CORS — allow the local frontend dev server (port 3000 / 5173)
# ---------------------------------------------------------------------------

# CORS is not configured here yet; add django-cors-headers when the
# frontend is implemented.

# ---------------------------------------------------------------------------
# Email — console backend for local development
# ---------------------------------------------------------------------------

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ---------------------------------------------------------------------------
# Development database check: warn if DATABASE_URL is not set
# ---------------------------------------------------------------------------

# DATABASE_URL is read from environment (docker-compose injects it).
# Falls back to the default defined in base.py if missing.

