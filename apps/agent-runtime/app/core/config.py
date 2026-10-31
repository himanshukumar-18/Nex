"""
NEX Agent Runtime — Application Configuration.

All settings are loaded from environment variables and validated at startup
using Pydantic Settings. Production environments strictly disallow insecure
or missing settings.
"""

from typing import Literal
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application metadata & environment
    app_name: str = "NEX Agent Runtime"
    app_version: str = "0.1.0"
    app_env: Literal["development", "production", "test"] = "development"
    app_debug: bool = False

    # API Documentation (disabled by default in internal service)
    docs_enabled: bool = False
    api_prefix: str = "/api/v1"

    # Backend service (internal Docker network DNS)
    backend_url: str = "http://backend:8000"
    backend_timeout_seconds: float = 10.0

    # Redis configuration (isolated runtime DB 1)
    redis_url: str = "redis://redis:6379/1"
    redis_connect_timeout_seconds: float = 2.0
    redis_socket_timeout_seconds: float = 2.0
    redis_max_connections: int = 50

    # Security & resource boundaries
    max_request_body_size_bytes: int = 10 * 1024 * 1024  # 10 MB bound
    cors_origins: list[str] = []

    # Inter-Service Authentication (Django Backend -> FastAPI Agent Runtime)
    internal_service_secret: str = "change-me-internal-service-secret-development"
    internal_service_secret_fallback: str | None = None

    @field_validator("internal_service_secret")
    @classmethod
    def validate_service_secret(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("internal_service_secret cannot be empty")
        return v

    @field_validator("backend_url")
    @classmethod
    def validate_backend_url(cls, v: str) -> str:
        v = v.strip()
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("backend_url must start with http:// or https://")
        return v

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        v = v.strip()
        if not (v.startswith("redis://") or v.startswith("rediss://")):
            raise ValueError("redis_url must start with redis:// or rediss://")
        return v

    @field_validator("backend_timeout_seconds", "redis_connect_timeout_seconds", "redis_socket_timeout_seconds")
    @classmethod
    def validate_positive_timeout(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Timeouts must be strictly positive floats")
        return v

    @field_validator("max_request_body_size_bytes")
    @classmethod
    def validate_body_size(cls, v: int) -> int:
        if v < 1024:
            raise ValueError("max_request_body_size_bytes must be at least 1024 bytes")
        return v


# Singleton settings instance initialized from environment
settings = Settings()

