"""
NEX Agent Runtime — Version 1 API Router.

Mounts versioned routes for agent execution, workflows, and runtime status.
All routes under /api/v1 require internal service authentication.
"""

import datetime
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.v1.schemas import (
    AgentTaskRequest,
    AgentTaskResponse,
    ServicePingRequest,
    ServicePingResponse,
)
from app.core.config import Settings, settings

api_v1_router = APIRouter(prefix=settings.api_prefix)


@api_v1_router.get("/status", tags=["Status"])
async def runtime_status(request: Request) -> JSONResponse:
    """
    Return basic service metadata and operating status.
    Protected by internal service authentication.
    """
    cfg: Settings = getattr(request.app.state, "settings", settings)
    return JSONResponse(
        status_code=200,
        content={
            "service": cfg.app_name,
            "version": cfg.app_version,
            "environment": cfg.app_env,
            "status": "operational",
        },
    )


@api_v1_router.post("/ping", response_model=ServicePingResponse, tags=["Internal Communication"])
async def service_ping(payload: ServicePingRequest) -> ServicePingResponse:
    """
    Inter-service ping endpoint invoked by Django backend to verify mutual authentication
    and round-trip payload serialization.
    """
    return ServicePingResponse(
        status="ok",
        service="nex-agent-runtime",
        echo_message=payload.message,
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )


@api_v1_router.post("/tasks/verify", response_model=AgentTaskResponse, tags=["Tasks"])
async def verify_task_contract(payload: AgentTaskRequest) -> AgentTaskResponse:
    """
    Validate and acknowledge a task execution request from the Django backend.
    """
    return AgentTaskResponse(
        task_id=payload.task_id,
        status="accepted",
        result={
            "action": payload.action,
            "parameter_count": len(payload.parameters),
            "acknowledged": True,
        },
    )
