"""NEX Django API Gateway Client.

Provides synchronous HTTP communication with the Django backend.
Enforces explicit timeouts, connection pooling, correlation ID tracking,
idempotent retries, and normalized error mapping.
"""

import time
import uuid
from contextlib import AbstractContextManager
from typing import Any

import httpx

from nex.client.contracts import BackendHealthStatus
from nex.client.exceptions import (
    NexClientAuthError,
    NexClientError,
    NexClientMalformedResponseError,
    NexClientNetworkError,
    NexClientResponseError,
    NexClientTimeoutError,
)
from nex.core.credentials import get_stored_token

DEFAULT_CONNECT_TIMEOUT: float = 5.0
DEFAULT_READ_TIMEOUT: float = 15.0
DEFAULT_WRITE_TIMEOUT: float = 10.0
DEFAULT_POOL_TIMEOUT: float = 5.0


class NexDjangoClient(AbstractContextManager["NexDjangoClient"]):
    """Synchronous HTTP client for interacting with the Django Core Backend."""

    def __init__(
        self,
        base_url: str = "http://localhost:8080/api/v1",
        *,
        api_key: str | None = None,
        timeout_seconds: float = DEFAULT_READ_TIMEOUT,
        retry_attempts: int = 1,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.retry_attempts = max(0, retry_attempts)

        self._timeout = httpx.Timeout(
            connect=DEFAULT_CONNECT_TIMEOUT,
            read=timeout_seconds,
            write=DEFAULT_WRITE_TIMEOUT,
            pool=DEFAULT_POOL_TIMEOUT,
        )

        self._limits = httpx.Limits(
            max_keepalive_connections=5,
            max_connections=10,
            keepalive_expiry=30.0,
        )

        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        """Lazily initialize client instance."""
        if self._client is None or self._client.is_closed:
            headers = {
                "Accept": "application/json",
                "User-Agent": "nex-cli/0.1.0",
            }
            token = self.api_key or get_stored_token()
            if token:
                headers["Authorization"] = f"Bearer {token}"

            self._client = httpx.Client(
                timeout=self._timeout,
                limits=self._limits,
                headers=headers,
                follow_redirects=False,
            )
        return self._client

    def close(self) -> None:
        """Close connection pool cleanly."""
        if self._client and not self._client.is_closed:
            self._client.close()
            self._client = None

    def __enter__(self) -> "NexDjangoClient":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def _build_url(self, path: str) -> str:
        """Construct full URL ensuring clean formatting."""
        clean_path = path if path.startswith("/") else f"/{path}"
        if clean_path.startswith("/health"):
            host_base = self.base_url.split("/api")[0]
            return f"{host_base}{clean_path}"
        return f"{self.base_url}{clean_path}"

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute HTTP request with correlation tracking and error normalization.

        Idempotent methods (GET, HEAD) retry up to retry_attempts times on transient connect errors.
        Non-idempotent methods (POST, PUT, DELETE, PATCH) NEVER retry automatically.
        """
        method_upper = method.upper()
        cid = correlation_id or f"nex-cli-{uuid.uuid4()}"
        headers = {"X-Correlation-Id": cid}
        url = self._build_url(path)
        client = self._get_client()

        is_idempotent = method_upper in {"GET", "HEAD", "OPTIONS"}
        max_attempts = (1 + self.retry_attempts) if is_idempotent else 1
        current_attempt = 0

        while current_attempt < max_attempts:
            current_attempt += 1
            try:
                response = client.request(
                    method=method_upper,
                    url=url,
                    params=params,
                    json=json,
                    headers=headers,
                )
                return self._handle_response(response, method_upper, path)

            except httpx.ConnectTimeout as err:
                if is_idempotent and current_attempt < max_attempts:
                    time.sleep(0.1)
                    continue
                raise NexClientTimeoutError(
                    f"Connection timed out connecting to NEX backend on {method_upper} {path}",
                    detail=str(err),
                ) from err

            except httpx.ReadTimeout as err:
                raise NexClientTimeoutError(
                    f"Read timeout after {self.timeout_seconds}s waiting for NEX backend response",
                    detail=str(err),
                ) from err

            except (httpx.ConnectError, httpx.NetworkError) as err:
                if is_idempotent and current_attempt < max_attempts:
                    time.sleep(0.1)
                    continue
                raise NexClientNetworkError(
                    f"Network error connecting to NEX backend: {err}",
                    detail=str(err),
                ) from err

            except httpx.HTTPError as err:
                raise NexClientError(
                    f"HTTP transport failure communicating with NEX backend: {err}",
                    detail=str(err),
                ) from err

        raise NexClientNetworkError(
            f"Failed to connect to NEX backend on {method_upper} {path} after {max_attempts} attempts."
        )

    def _handle_response(
        self,
        response: httpx.Response,
        method: str,
        path: str,
    ) -> dict[str, Any]:
        """Normalize response and handle error envelopes."""
        status_code = response.status_code

        # Attempt to parse JSON body
        body_data: dict[str, Any] = {}
        if response.content:
            try:
                body_data = response.json()
            except Exception as err:
                if not response.is_success:
                    raise NexClientMalformedResponseError(
                        f"NEX backend returned HTTP {status_code} with non-JSON body on {method} {path}",
                        detail=response.text[:200],
                    ) from err
                body_data = {"raw": response.text}

        if response.is_success:
            return body_data

        # Extract normalized error details if present
        error_dict = body_data.get("error", {})
        code = error_dict.get("code") if isinstance(error_dict, dict) else None
        message = (
            error_dict.get("message")
            if isinstance(error_dict, dict)
            else body_data.get("message")
            or body_data.get("detail")
            or f"HTTP {status_code}"
        )
        detail = error_dict.get("detail") if isinstance(error_dict, dict) else None

        if status_code in {401, 403}:
            raise NexClientAuthError(
                f"Authentication failed ({message}) on {method} {path}",
                code=code or "AUTHENTICATION_FAILED",
                detail=detail,
            )

        raise NexClientResponseError(
            f"NEX backend error ({code or status_code}): {message}",
            status_code=status_code,
            code=code or f"HTTP_{status_code}",
            detail=detail,
        )

    def check_health(self) -> BackendHealthStatus:
        """Probe backend liveness."""
        data = self.request("GET", "/health/")
        return BackendHealthStatus.model_validate(data)

    def get_runs(self, limit: int = 10) -> list[dict[str, Any]]:
        """Fetch historical task runs from backend."""
        data = self.request("GET", "/runs/", params={"limit": limit})
        runs = data.get("runs") if isinstance(data, dict) else None
        if isinstance(runs, list):
            return [r for r in runs if isinstance(r, dict)]
        return []

    def get_run(self, run_id: str) -> dict[str, Any]:
        """Fetch details of a specific task run from backend."""
        return self.request("GET", f"/runs/{run_id}/")
