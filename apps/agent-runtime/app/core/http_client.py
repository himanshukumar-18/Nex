"""
NEX Agent Runtime — Inter-Service HTTP Client Lifecycle & Dependency.

Manages the httpx.AsyncClient pool used for communication with the Django backend.
Automatically propagates the active X-Correlation-Id header on outbound requests.
"""

import logging
from typing import AsyncIterator, Optional
import httpx

from app.core.config import settings
from app.core.logging import get_correlation_id

logger = logging.getLogger("agent_runtime.http_client")

_http_client: Optional[httpx.AsyncClient] = None


async def _propagate_correlation_id(request: httpx.Request) -> None:
    """Outbound request hook to inject the active X-Correlation-Id header."""
    cid = get_correlation_id()
    if cid and cid != "-":
        request.headers["X-Correlation-Id"] = cid


async def init_http_client() -> httpx.AsyncClient:
    """
    Initialize the singleton async HTTP client.
    Called during application lifespan startup.
    """
    global _http_client
    if _http_client is not None:
        return _http_client

    logger.info("Initializing httpx AsyncClient for inter-service communication")
    _http_client = httpx.AsyncClient(
        base_url=settings.backend_url,
        timeout=httpx.Timeout(settings.backend_timeout_seconds, connect=3.0),
        event_hooks={"request": [_propagate_correlation_id]},
    )
    return _http_client


async def close_http_client() -> None:
    """
    Gracefully close the HTTP client pool.
    Called during application lifespan shutdown.
    """
    global _http_client
    if _http_client is not None:
        logger.info("Closing httpx AsyncClient")
        await _http_client.aclose()
        _http_client = None


async def check_backend_health() -> bool:
    """
    Check if the Django backend liveness endpoint is reachable.
    Used by the readiness probe.
    """
    if _http_client is None:
        return False
    try:
        response = await _http_client.get("/health/", timeout=2.0)
        return response.status_code == 200
    except Exception as exc:
        logger.warning("Backend health check failed: %s", exc)
        return False


async def get_http_client() -> AsyncIterator[httpx.AsyncClient]:
    """
    FastAPI dependency for accessing the inter-service HTTP client.
    Raises RuntimeError if HTTP client has not been initialized.
    """
    if _http_client is None:
        raise RuntimeError("HTTP client is not initialized in application lifespan")
    yield _http_client

