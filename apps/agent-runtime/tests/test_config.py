"""
NEX Agent Runtime — Configuration Unit Tests.
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_default_settings():
    """Verify default configuration values."""
    s = Settings()
    assert s.app_name == "NEX Agent Runtime"
    assert s.app_version == "0.1.0"
    assert s.app_env in ["development", "production", "test"]
    assert s.backend_url.startswith("http")
    assert s.redis_url.startswith("redis")
    assert s.backend_timeout_seconds > 0
    assert s.redis_connect_timeout_seconds > 0
    assert s.max_request_body_size_bytes >= 1024


def test_invalid_backend_url():
    """Verify that an invalid backend_url scheme raises ValidationError."""
    with pytest.raises(ValidationError) as exc:
        Settings(backend_url="ftp://backend:8000")
    assert "backend_url must start with http:// or https://" in str(exc.value)


def test_invalid_redis_url():
    """Verify that an invalid redis_url scheme raises ValidationError."""
    with pytest.raises(ValidationError) as exc:
        Settings(redis_url="postgres://redis:6379/1")
    assert "redis_url must start with redis:// or rediss://" in str(exc.value)


def test_invalid_timeouts():
    """Verify that non-positive timeouts raise ValidationError."""
    with pytest.raises(ValidationError) as exc:
        Settings(backend_timeout_seconds=0.0)
    assert "Timeouts must be strictly positive" in str(exc.value)

    with pytest.raises(ValidationError) as exc:
        Settings(redis_connect_timeout_seconds=-1.0)
    assert "Timeouts must be strictly positive" in str(exc.value)


def test_invalid_body_size():
    """Verify that a body size limit below 1024 bytes is rejected."""
    with pytest.raises(ValidationError) as exc:
        Settings(max_request_body_size_bytes=500)
    assert "max_request_body_size_bytes must be at least 1024" in str(exc.value)

