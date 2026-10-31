"""
NEX Agent Runtime — Internal Service Authentication Middleware.

Enforces shared-secret service-to-service authentication between Django Backend
and FastAPI Agent Runtime.
  - Verifies credentials using constant-time comparison (secrets.compare_digest).
  - Supports zero-downtime key rotation via primary and fallback keys.
  - Bypasses public container health probes (/health, /health/live).
  - Returns normalized NEX error responses (HTTP 401 UNAUTHORIZED).
  - Never logs secrets, tokens, or authorization headers.
"""

import logging
import secrets
from typing import Callable, Set
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.core.logging import get_correlation_id

logger = logging.getLogger("agent_runtime.auth")

SERVICE_KEY_HEADER = "x-internal-service-key"
AUTHORIZATION_HEADER = "authorization"
BEARER_PREFIX = "bearer "

# Endpoints exempted from service key verification (container liveness probes)
EXEMPT_PATHS: Set[str] = {
    "/health",
    "/health/live",
}


def extract_service_key(request: Request) -> str | None:
    """Extract internal service secret from custom header or Bearer authorization."""
    # 1. Custom internal header
    custom_key = request.headers.get(SERVICE_KEY_HEADER)
    if custom_key:
        return custom_key.strip()

    # 2. Authorization: Bearer <key>
    auth_header = request.headers.get(AUTHORIZATION_HEADER)
    if auth_header and auth_header.lower().startswith(BEARER_PREFIX):
        return auth_header[len(BEARER_PREFIX):].strip()

    return None


class InternalServiceAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware verifying that requests originate from an authorized internal service (Django).
    Constant-time comparison protects against timing attacks.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        # Exempt public container liveness probes
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        # Retrieve active configuration from application state if available
        cfg = getattr(request.app.state, "settings", settings)
        primary_secret: str = cfg.internal_service_secret
        fallback_secret: str | None = cfg.internal_service_secret_fallback

        provided_key = extract_service_key(request)

        if not provided_key:
            logger.warning(
                "Unauthorized internal request to %s %s: missing service credentials [correlation_id=%s]",
                request.method,
                request.url.path,
                get_correlation_id(),
            )
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": "Missing internal service authentication credentials",
                        "detail": None,
                    }
                },
            )

        # Constant-time comparison against primary key
        is_valid = secrets.compare_digest(provided_key, primary_secret)

        # Constant-time comparison against rotation fallback key if configured
        if not is_valid and fallback_secret:
            is_valid = secrets.compare_digest(provided_key, fallback_secret)

        if not is_valid:
            logger.warning(
                "Unauthorized internal request to %s %s: invalid service credentials [correlation_id=%s]",
                request.method,
                request.url.path,
                get_correlation_id(),
            )
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": "Invalid internal service authentication credentials",
                        "detail": None,
                    }
                },
            )

        return await call_next(request)

