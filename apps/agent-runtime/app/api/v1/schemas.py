"""
NEX Agent Runtime — Version 1 API Request and Response Schemas.

Pydantic models defining strict validation contracts for inter-service communication
between Django Backend and FastAPI Agent Runtime.
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ServicePingRequest(BaseModel):
    """Payload sent by Django to verify inter-service connectivity and credentials."""

    message: str = Field(..., min_length=1, max_length=256, description="Test message")
    client_service: str = Field(default="django-backend", min_length=1, max_length=64)


class ServicePingResponse(BaseModel):
    """Response returned to Django upon successful service ping."""

    status: str = Field(default="ok")
    service: str = Field(default="nex-agent-runtime")
    echo_message: str
    timestamp: str


class AgentTaskRequest(BaseModel):
    """Contract for initiating or verifying agent task execution requests from Django."""

    task_id: str = Field(..., min_length=1, max_length=64, description="Unique task identifier")
    action: str = Field(..., min_length=1, max_length=64, description="Action to perform")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action-specific parameters")


class AgentTaskResponse(BaseModel):
    """Contract returned for agent task requests."""

    task_id: str
    status: str
    result: Optional[Dict[str, Any]] = None

