"""NEX Configuration Schema.

Strict Pydantic models governing user, project, and runtime CLI preferences.
"""

from typing import Literal

from pydantic import BaseModel, Field


class GeneralConfig(BaseModel):
    """General AI model preferences and developer identity defaults."""

    default_provider: str = Field(
        default="google", description="Default AI provider family"
    )
    default_model: str = Field(
        default="gemini-2.0-flash", description="Default model identifier"
    )


class ApiConfig(BaseModel):
    """Backend connection and timeout configuration."""

    base_url: str = Field(
        default="http://localhost:8080/api/v1",
        description="Public Django API gateway base URL",
    )
    timeout_seconds: float = Field(
        default=15.0,
        ge=1.0,
        le=120.0,
        description="HTTP request timeout in seconds",
    )
    retry_attempts: int = Field(
        default=1,
        ge=0,
        le=3,
        description="Idempotent retry attempts on transient network disconnect",
    )


class OutputConfig(BaseModel):
    """Terminal display and formatting settings."""

    format: Literal["terminal", "json"] = Field(
        default="terminal",
        description="Output rendering format",
    )
    verbose: bool = Field(default=False, description="Enable verbose diagnostic output")
    color: bool = Field(default=True, description="Enable rich ANSI color formatting")


class ExecutionConfig(BaseModel):
    """Safety and execution environment policies."""

    mode: Literal["hybrid", "local", "sandbox"] = Field(
        default="hybrid",
        description="Execution mode architecture",
    )
    require_approval: bool = Field(
        default=True,
        description="Enforce interactive developer approval for sensitive actions",
    )


class ProjectMetadata(BaseModel):
    """Project-specific metadata stored in project config."""

    project_id: str | None = Field(
        default=None, description="Remote backend project UUID"
    )
    name: str | None = Field(default=None, description="Project name")
    version: str = Field(default="0.1.0", description="Configuration schema version")


class NexConfig(BaseModel):
    """Unified NEX Configuration model."""

    general: GeneralConfig = Field(default_factory=GeneralConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    project: ProjectMetadata = Field(default_factory=ProjectMetadata)
