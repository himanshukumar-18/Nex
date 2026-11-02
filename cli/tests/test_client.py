"""Tests for NexDjangoClient HTTP communication, retry policies, and error handling."""

from unittest.mock import MagicMock, patch

import httpx
import pytest
from nex.client.django import NexDjangoClient
from nex.client.exceptions import (
    NexClientAuthError,
    NexClientResponseError,
    NexClientTimeoutError,
)


def test_build_url_routes_health_to_host_root() -> None:
    """Ensure /health/ probes strip /api/v1 to target backend health endpoints correctly."""
    client = NexDjangoClient(base_url="http://localhost:8080/api/v1")

    assert client._build_url("/health/") == "http://localhost:8080/health/"
    assert client._build_url("/health/ready/") == "http://localhost:8080/health/ready/"
    assert client._build_url("/runs/") == "http://localhost:8080/api/v1/runs/"


def test_correlation_id_and_auth_headers() -> None:
    """Verify X-Correlation-Id and Authorization headers are injected."""
    client = NexDjangoClient(
        base_url="http://localhost:8080/api/v1", api_key="secret-key"
    )

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.is_success = True
    mock_response.status_code = 200
    mock_response.content = b'{"status": "ok"}'
    mock_response.json.return_value = {"status": "ok"}

    with patch.object(httpx.Client, "request", return_value=mock_response) as mock_req:
        res = client.request("GET", "/health/", correlation_id="test-cid-123")
        assert res == {"status": "ok"}

        mock_req.assert_called_once()
        _, kwargs = mock_req.call_args
        assert kwargs["headers"]["X-Correlation-Id"] == "test-cid-123"


def test_idempotent_get_retries_once_on_connect_timeout() -> None:
    """Ensure idempotent GET retries on transient connection timeout."""
    client = NexDjangoClient(base_url="http://localhost:8080/api/v1", retry_attempts=1)

    mock_success = MagicMock(spec=httpx.Response)
    mock_success.is_success = True
    mock_success.status_code = 200
    mock_success.content = b'{"status": "healthy"}'
    mock_success.json.return_value = {"status": "healthy"}

    # First attempt times out, second succeeds
    with patch.object(
        httpx.Client,
        "request",
        side_effect=[httpx.ConnectTimeout("connection failed"), mock_success],
    ) as mock_req:
        res = client.request("GET", "/health/")
        assert res == {"status": "healthy"}
        assert mock_req.call_count == 2


def test_non_idempotent_post_never_retries() -> None:
    """Ensure POST requests fail immediately without automatic retry on connection timeout."""
    client = NexDjangoClient(base_url="http://localhost:8080/api/v1", retry_attempts=2)

    with patch.object(
        httpx.Client,
        "request",
        side_effect=httpx.ConnectTimeout("connection failed"),
    ) as mock_req:
        with pytest.raises(NexClientTimeoutError):
            client.request("POST", "/runs/", json={"task": "build"})

        # Only 1 attempt must be made for non-idempotent POST
        assert mock_req.call_count == 1


def test_client_auth_error_mapping() -> None:
    """Ensure 401/403 responses raise NexClientAuthError with details."""
    client = NexDjangoClient(base_url="http://localhost:8080/api/v1")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.is_success = False
    mock_resp.status_code = 401
    mock_resp.content = (
        b'{"error": {"code": "TOKEN_EXPIRED", "message": "Token expired"}}'
    )
    mock_resp.json.return_value = {
        "error": {"code": "TOKEN_EXPIRED", "message": "Token expired"}
    }

    with patch.object(httpx.Client, "request", return_value=mock_resp):
        with pytest.raises(NexClientAuthError) as exc_info:
            client.request("GET", "/runs/")

        assert exc_info.value.code == "TOKEN_EXPIRED"
        assert "Token expired" in exc_info.value.message


def test_client_response_error_normalization() -> None:
    """Ensure non-auth error responses raise NexClientResponseError."""
    client = NexDjangoClient(base_url="http://localhost:8080/api/v1")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.is_success = False
    mock_resp.status_code = 500
    mock_resp.content = (
        b'{"error": {"code": "INTERNAL_ERROR", "message": "Database error"}}'
    )
    mock_resp.json.return_value = {
        "error": {"code": "INTERNAL_ERROR", "message": "Database error"}
    }

    with patch.object(httpx.Client, "request", return_value=mock_resp):
        with pytest.raises(NexClientResponseError) as exc_info:
            client.request("GET", "/runs/")

        assert exc_info.value.status_code == 500
        assert exc_info.value.code == "INTERNAL_ERROR"
