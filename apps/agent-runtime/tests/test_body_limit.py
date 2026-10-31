"""
NEX Agent Runtime — Request Body Size Enforcement Unit Tests.

Validates Section 2.F requirements:
  - Enforces actual streamed body size (not just Content-Length header).
  - Handles missing Content-Length on chunked/streamed transfers.
  - Rejects oversized streamed requests immediately with HTTP 413.
"""

from typing import AsyncIterator
import httpx
import pytest


@pytest.mark.asyncio
async def test_stated_content_length_oversized(client: httpx.AsyncClient):
    """Verify fast-path rejection when stated Content-Length exceeds allowable limit."""
    res = await client.post(
        "/api/v1/ping",
        headers={"Content-Length": "5242880"},  # 5 MB > 1 MB test limit
        content=b"",
    )
    assert res.status_code == 413
    data = res.json()
    assert data["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert "exceeds maximum allowed size" in data["error"]["message"]


@pytest.mark.asyncio
async def test_streamed_chunked_body_oversized(client: httpx.AsyncClient):
    """Verify that streamed requests without Content-Length exceeding limit are rejected with HTTP 413."""
    chunk = b"X" * 65536  # 64 KB

    async def stream_generator() -> AsyncIterator[bytes]:
        # Send 20 chunks = 1.28 MB (> 1 MB test limit)
        for _ in range(20):
            yield chunk

    # httpx streaming without content-length header
    res = await client.post(
        "/api/v1/ping",
        content=stream_generator(),
        headers={"Content-Type": "application/json"},
    )
    assert res.status_code == 413
    data = res.json()
    assert data["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert data["error"]["detail"]["max_bytes"] == 1048576
    assert data["error"]["detail"]["received_bytes"] > 1048576


@pytest.mark.asyncio
async def test_streamed_chunked_body_within_limit(client: httpx.AsyncClient):
    """Verify that valid streamed requests within size boundary are processed successfully."""
    # Valid small JSON payload streamed in chunks
    chunks = [b'{"message": "valid ', b'streamed payload"}']

    async def stream_generator() -> AsyncIterator[bytes]:
        for c in chunks:
            yield c

    res = await client.post(
        "/api/v1/ping",
        content=stream_generator(),
        headers={"Content-Type": "application/json"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["echo_message"] == "valid streamed payload"


@pytest.mark.asyncio
async def test_malformed_content_length_rejected(client: httpx.AsyncClient):
    """Verify that invalid/malformed Content-Length header returns HTTP 400."""
    res = await client.post(
        "/api/v1/ping",
        headers={"Content-Length": "not-valid-number"},
        content=b"",
    )
    assert res.status_code == 400
    data = res.json()
    assert data["error"]["code"] == "BAD_REQUEST"

