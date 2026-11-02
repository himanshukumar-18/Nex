"""NEX Backend API Contracts.

Pydantic models representing standardized request and response structures
exchanged with the Django public API gateway.
"""

from typing import Any

from pydantic import BaseModel


class BackendErrorDetail(BaseModel):
    """Normalized error envelope returned by Django backend."""

    code: str
    message: str
    detail: Any | None = None


class BackendErrorEnvelope(BaseModel):
    """Root error wrapper."""

    error: BackendErrorDetail


class BackendHealthStatus(BaseModel):
    """Response returned by /health/ and /health/ready/ probes."""

    status: str
    database: str | None = None
    cache: str | None = None


class RunSummary(BaseModel):
    """Task run summary contract for historical run inspection."""

    id: str
    task_type: str
    status: str
    created_at: str
    duration_ms: int | None = None
    summary: str | None = None
