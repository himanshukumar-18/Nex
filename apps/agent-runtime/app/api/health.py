"""
NEX Agent Runtime — Liveness and Readiness Health Probes.

Decouples liveness (is the process responsive?) from readiness
(are dependencies such as Redis and the Django backend reachable?).
Neither probe exposes secrets, environment variables, or internal stack traces.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.http_client import check_backend_health
from app.core.redis import check_redis_health

router = APIRouter(tags=["Health"])


@router.get("/health", include_in_schema=False)
@router.get("/health/live", include_in_schema=False)
async def liveness_probe() -> JSONResponse:
    """
    Liveness probe.
    Returns HTTP 200 {"status": "ok", "service": "agent-runtime"} when the ASGI process is running.
    Does not perform I/O against external dependencies.
    """
    return JSONResponse(
        status_code=200,
        content={"status": "ok", "service": "agent-runtime"},
    )


@router.get("/health/ready", include_in_schema=False)
async def readiness_probe() -> JSONResponse:
    """
    Readiness probe.
    Checks connectivity to Redis (DB 1) and the Django backend service.
    Returns HTTP 200 when ready to accept traffic, or HTTP 503 if critical dependencies are down.
    """
    redis_healthy = await check_redis_health()
    backend_healthy = await check_backend_health()

    components = {
        "redis": "ok" if redis_healthy else "unavailable",
        "backend": "ok" if backend_healthy else "unavailable",
    }

    # Redis is critical for agent runtime state; backend is required for inter-service workflows
    all_ready = redis_healthy and backend_healthy
    status_code = 200 if all_ready else 503
    status_text = "ready" if all_ready else "degraded"

    return JSONResponse(
        status_code=status_code,
        content={
            "status": status_text,
            "service": "agent-runtime",
            "components": components,
        },
    )

