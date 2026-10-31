"""
NEX Agent Runtime — Health Probes Unit Tests.
"""

from unittest.mock import AsyncMock, patch
import httpx
import pytest


@pytest.mark.asyncio
async def test_liveness_endpoints(client: httpx.AsyncClient):
    """Verify that /health and /health/live return 200 without querying dependencies."""
    res = await client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["service"] == "agent-runtime"

    res_live = await client.get("/health/live")
    assert res_live.status_code == 200
    assert res_live.json() == data


@pytest.mark.asyncio
async def test_readiness_all_healthy(client: httpx.AsyncClient):
    """Verify readiness returns 200 when both Redis and Backend are responsive."""
    with patch("app.api.health.check_redis_health", new_callable=AsyncMock) as mock_redis, \
         patch("app.api.health.check_backend_health", new_callable=AsyncMock) as mock_backend:
        mock_redis.return_value = True
        mock_backend.return_value = True

        res = await client.get("/health/ready")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ready"
        assert data["components"]["redis"] == "ok"
        assert data["components"]["backend"] == "ok"


@pytest.mark.asyncio
async def test_readiness_redis_failure(client: httpx.AsyncClient):
    """Verify readiness returns 503 when Redis is unavailable."""
    with patch("app.api.health.check_redis_health", new_callable=AsyncMock) as mock_redis, \
         patch("app.api.health.check_backend_health", new_callable=AsyncMock) as mock_backend:
        mock_redis.return_value = False
        mock_backend.return_value = True

        res = await client.get("/health/ready")
        assert res.status_code == 503
        data = res.json()
        assert data["status"] == "degraded"
        assert data["components"]["redis"] == "unavailable"
        assert data["components"]["backend"] == "ok"


@pytest.mark.asyncio
async def test_readiness_backend_failure(client: httpx.AsyncClient):
    """Verify readiness returns 503 when Django backend is unreachable."""
    with patch("app.api.health.check_redis_health", new_callable=AsyncMock) as mock_redis, \
         patch("app.api.health.check_backend_health", new_callable=AsyncMock) as mock_backend:
        mock_redis.return_value = True
        mock_backend.return_value = False

        res = await client.get("/health/ready")
        assert res.status_code == 503
        data = res.json()
        assert data["status"] == "degraded"
        assert data["components"]["redis"] == "ok"
        assert data["components"]["backend"] == "unavailable"

