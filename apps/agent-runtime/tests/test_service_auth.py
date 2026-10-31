"""
NEX Agent Runtime — Internal Service Authentication Unit Tests.
"""

import httpx
import pytest

from app.core.config import Settings


@pytest.mark.asyncio
async def test_unauthenticated_liveness_probe_accessible(unauth_client: httpx.AsyncClient):
    """Verify that liveness probe is accessible without credentials (for container health checks)."""
    res = await unauth_client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    res_live = await unauth_client.get("/health/live")
    assert res_live.status_code == 200
    assert res_live.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_unauthenticated_api_request_rejected(unauth_client: httpx.AsyncClient):
    """Verify that internal API endpoints reject unauthenticated requests with HTTP 401."""
    res = await unauth_client.get("/api/v1/status")
    assert res.status_code == 401
    data = res.json()
    assert data["error"]["code"] == "UNAUTHORIZED"
    assert "Missing internal service authentication credentials" in data["error"]["message"]


@pytest.mark.asyncio
async def test_invalid_credentials_rejected(unauth_client: httpx.AsyncClient):
    """Verify that invalid service credentials return HTTP 401 with standard error envelope."""
    res = await unauth_client.get("/api/v1/status", headers={"X-Internal-Service-Key": "wrong-secret-token"})
    assert res.status_code == 401
    data = res.json()
    assert data["error"]["code"] == "UNAUTHORIZED"
    assert "Invalid internal service authentication credentials" in data["error"]["message"]


@pytest.mark.asyncio
async def test_valid_primary_key_accepted(unauth_client: httpx.AsyncClient, test_settings: Settings):
    """Verify that the primary configured internal secret allows access."""
    res = await unauth_client.get(
        "/api/v1/status",
        headers={"X-Internal-Service-Key": test_settings.internal_service_secret},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "operational"


@pytest.mark.asyncio
async def test_valid_bearer_authorization_accepted(unauth_client: httpx.AsyncClient, test_settings: Settings):
    """Verify that Authorization: Bearer <secret> format is also accepted."""
    res = await unauth_client.get(
        "/api/v1/status",
        headers={"Authorization": f"Bearer {test_settings.internal_service_secret}"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "operational"


@pytest.mark.asyncio
async def test_fallback_rotation_key_accepted(unauth_client: httpx.AsyncClient, test_settings: Settings):
    """Verify that secondary fallback key allows access during zero-downtime secret rotation."""
    assert test_settings.internal_service_secret_fallback is not None
    res = await unauth_client.get(
        "/api/v1/status",
        headers={"X-Internal-Service-Key": test_settings.internal_service_secret_fallback},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "operational"

