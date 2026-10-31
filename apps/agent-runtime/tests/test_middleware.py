"""
NEX Agent Runtime — Middleware Unit Tests.
"""

import httpx
import pytest


@pytest.mark.asyncio
async def test_correlation_id_propagated(client: httpx.AsyncClient):
    """Verify that a valid incoming X-Correlation-Id is returned in response headers."""
    cid = "test-corr-id-12345"
    res = await client.get("/health", headers={"X-Correlation-Id": cid})
    assert res.status_code == 200
    assert res.headers.get("X-Correlation-Id") == cid
    assert "X-Process-Time-Ms" in res.headers


@pytest.mark.asyncio
async def test_correlation_id_generated_when_missing(client: httpx.AsyncClient):
    """Verify that a missing X-Correlation-Id triggers generation of a valid 32-char hex ID."""
    res = await client.get("/health")
    assert res.status_code == 200
    cid = res.headers.get("X-Correlation-Id")
    assert cid is not None
    assert len(cid) == 32
    assert "X-Process-Time-Ms" in res.headers


@pytest.mark.asyncio
async def test_correlation_id_sanitized_when_invalid(client: httpx.AsyncClient):
    """Verify that an invalid correlation ID (special chars, too long) is replaced with a generated UUID."""
    invalid_cid = "bad<script>id" * 10
    res = await client.get("/health", headers={"X-Correlation-Id": invalid_cid})
    assert res.status_code == 200
    cid = res.headers.get("X-Correlation-Id")
    assert cid != invalid_cid
    assert len(cid) == 32


@pytest.mark.asyncio
async def test_payload_size_limit_rejection(client: httpx.AsyncClient):
    """Verify that requests exceeding max_request_body_size_bytes return 413 Payload Too Large."""
    # Test setting has max_request_body_size_bytes = 1 MB (1048576)
    oversized_length = 2 * 1024 * 1024
    res = await client.post(
        "/api/v1/status",
        headers={"Content-Length": str(oversized_length)},
        content=b"",
    )
    assert res.status_code == 413
    data = res.json()
    assert data["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert "exceeds maximum allowed size" in data["error"]["message"]


@pytest.mark.asyncio
async def test_malformed_content_length_rejection(client: httpx.AsyncClient):
    """Verify that a malformed Content-Length header returns 400 Bad Request."""
    res = await client.post(
        "/api/v1/status",
        headers={"Content-Length": "not-a-number"},
        content=b"",
    )
    assert res.status_code == 400
    data = res.json()
    assert data["error"]["code"] == "BAD_REQUEST"

