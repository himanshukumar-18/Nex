"""
NEX Backend — root URL configuration.

URL structure:
  /health/          — Liveness probe (process alive, no DB query)
  /health/live/     — Liveness probe alias
  /health/ready/    — Readiness probe (database connectivity)
  /api/v1/          — REST API version 1 (domain endpoints added per phase)

All API endpoints are versioned under /api/v1/ and namespaced as "api_v1".
New domain applications (accounts, projects, repositories) register their
routes by adding an include() inside apps/api/urls.py.

Design decisions:
  - Health endpoints are outside /api/v1/ so they can be reached by
    infrastructure probes without API version negotiation.
  - The API namespace prevents URL name collisions across domain apps.
  - No trailing-slash redirect: strict=True is the default; all URLs in this
    project include explicit trailing slashes.
"""

from django.urls import include, path

from .health import health, readiness

urlpatterns = [
    # ──────────────────────────────────────────────────────────────────────
    # Infrastructure probes — not versioned, no authentication required
    # ──────────────────────────────────────────────────────────────────────
    path("health/", health, name="health_liveness"),
    path("health/live/", health, name="health_liveness_alias"),
    path("health/ready/", readiness, name="health_readiness"),
    # ──────────────────────────────────────────────────────────────────────
    # REST API — versioned; all domain routes live under apps/api/urls.py
    # ──────────────────────────────────────────────────────────────────────
    path("api/v1/", include("apps.api.urls", namespace="api_v1")),
]
