"""
NEX Agent Runtime — Version 1 API Unit Tests.
"""

import httpx
import pytest


@pytest.mark.asyncio
async def test_runtime_status_endpoint(client: httpx.AsyncClient):
    """Verify that /api/v1/status returns service metadata and operational status."""
    res = await client.get("/api/v1/status")
    assert res.status_code == 200
    data = res.json()
    assert data["service"] == "NEX Agent Runtime (Test)"
    assert data["version"] == "0.1.0"
    assert data["status"] == "operational"
    assert data["environment"] == "test"

