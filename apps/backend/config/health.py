"""
NEX Backend — health and readiness endpoints.

Distinguishes between:
  - Liveness (/health/, /health/live/):
      Confirms the HTTP worker process is responsive.
      Zero external queries. Cheap and lightweight.
  - Readiness (/health/ready/):
      Confirms database and critical dependency connectivity.
      Returns HTTP 200 when ready, HTTP 503 when dependencies are unreachable.
      Never leaks connection strings, credentials, or internal stack traces.
"""

import json
import logging

from django.db import connection
from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)


def health(request: HttpRequest) -> HttpResponse:
    """Liveness probe — confirms the application process is alive."""
    body = json.dumps({"status": "ok"})
    return HttpResponse(body, content_type="application/json", status=200)


def readiness(request: HttpRequest) -> HttpResponse:
    """Readiness probe — confirms database connectivity safely."""
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            cursor.fetchone()
        body = json.dumps({"status": "ready", "database": "connected"})
        return HttpResponse(body, content_type="application/json", status=200)
    except Exception:
        # Never leak connection strings, hostnames, or internal stack traces to the caller
        logger.warning("Readiness check failed: database connectivity error", exc_info=False)
        body = json.dumps({"status": "unhealthy", "database": "unavailable"})
        return HttpResponse(body, content_type="application/json", status=503)
