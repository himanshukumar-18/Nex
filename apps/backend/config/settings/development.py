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
# CORS — local development overrides
# ---------------------------------------------------------------------------

# Allow local Vite dev server ports (3000 container/host, 5173 standalone)
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://0.0.0.0:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://0.0.0.0:5173",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://0.0.0.0:8080",
]

# ---------------------------------------------------------------------------
# Email — console backend for local development
# ---------------------------------------------------------------------------

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ---------------------------------------------------------------------------
# Development database check: warn if DATABASE_URL is not set
# ---------------------------------------------------------------------------

# DATABASE_URL is read from environment (docker-compose injects it).
# Falls back to the default defined in base.py if missing.

