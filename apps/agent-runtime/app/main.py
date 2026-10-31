"""
NEX Agent Runtime — FastAPI Application Entry Point.

Bootstraps the dedicated internal AI execution runtime with:
  - Modern async lifespan management (Redis connection pool & inter-service HTTP client)
  - Structured JSON logging to stdout with correlation ID tracking
  - Correlation ID and request size limit middlewares
  - Centralized exception handlers for consistent normalized error envelopes
  - Liveness (/health, /health/live) and Readiness (/health/ready) health probes
  - Versioned API routing (/api/v1/)
  - Controlled security headers and disabled public documentation

The agent-runtime is an internal service. It is reachable only within the
Docker internal network and communicates with the Django backend.
"""

from contextlib import asynccontextmanager
import logging
from typing import AsyncIterator, Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_v1_router, health_router
from app.core.auth import InternalServiceAuthMiddleware
from app.core.config import Settings, settings as global_settings
from app.core.exceptions import register_exception_handlers
from app.core.http_client import close_http_client, init_http_client
from app.core.logging import setup_logging
from app.core.middleware import CorrelationIdMiddleware, RequestBodyLimitMiddleware
from app.core.redis import close_redis_pool, init_redis_pool

logger = logging.getLogger("agent_runtime")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Manage application lifecycle startup and shutdown events.
    Initializes and cleans up Redis and HTTP connection pools.
    """
    cfg: Settings = getattr(app.state, "settings", global_settings)
    log_level = "DEBUG" if cfg.app_debug else "INFO"
    setup_logging(log_level=log_level, app_env=cfg.app_env)

    logger.info("Agent runtime starting up [env=%s, version=%s]", cfg.app_env, cfg.app_version)

    # Initialize connection pools
    await init_redis_pool()
    await init_http_client()

    yield

    # Clean up connection pools gracefully
    logger.info("Agent runtime shutting down")
    await close_http_client()
    await close_redis_pool()


def create_app(custom_settings: Optional[Settings] = None) -> FastAPI:
    """
    Application factory for the NEX Agent Runtime.
    Allows injecting custom configuration for unit testing.
    """
    cfg = custom_settings or global_settings

    app = FastAPI(
        title=cfg.app_name,
        version=cfg.app_version,
        docs_url="/docs" if cfg.docs_enabled else None,
        redoc_url="/redoc" if cfg.docs_enabled else None,
        openapi_url="/openapi.json" if cfg.docs_enabled else None,
        lifespan=lifespan,
    )

    # Store settings in application state
    app.state.settings = cfg

    # -----------------------------------------------------------------------
    # Middlewares (ordered: outer-most executes first)
    # -----------------------------------------------------------------------

    # CORS middleware (restricted to explicitly configured origins)
    if cfg.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cfg.cors_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["*"],
        )

    # Internal service authentication (Django -> FastAPI)
    app.add_middleware(InternalServiceAuthMiddleware)

    # Request body size boundary (HTTP 413)
    app.add_middleware(RequestBodyLimitMiddleware, max_bytes=cfg.max_request_body_size_bytes)

    # Correlation ID tracking and header injection
    app.add_middleware(CorrelationIdMiddleware)

    # -----------------------------------------------------------------------
    # Centralized Exception Handlers
    # -----------------------------------------------------------------------
    register_exception_handlers(app)

    # -----------------------------------------------------------------------
    # Routers
    # -----------------------------------------------------------------------
    app.include_router(health_router)
    app.include_router(api_v1_router)

    return app


# Default ASGI application instance for Uvicorn
app = create_app()
