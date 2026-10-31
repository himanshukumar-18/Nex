"""
NEX Backend — Dedicated FastAPI Agent Runtime Internal Client.

Manages HTTP communication from the Django Backend to the internal FastAPI Agent Runtime:
  - Connection pooling with httpx.Client and bounded socket/connect timeouts.
  - Automatic X-Correlation-Id header propagation from ContextVar / request context.
  - Constant-time secret service authentication header (X-Internal-Service-Key).
  - Path sanitization to prevent arbitrary URL forwarding and SSRF.
  - Safe retry policy: exactly 1 retry for transient network drops on idempotent GETs;
    zero retries for non-idempotent operations (POST/PUT/DELETE).
  - Domain exceptions normalizing downstream timeouts, outages, and 4xx/5xx responses.
"""

import json
import logging
import time
from typing import Any, Dict, Optional
from urllib.parse import urljoin
from django.conf import settings
import httpx

from apps.api.middleware import get_correlation_id
from apps.api.runtime_contracts import (
    AgentTaskRequestContract,
    AgentTaskResponseContract,
    ServicePingRequestContract,
    ServicePingResponseContract,
)

logger = logging.getLogger("apps.api.runtime_client")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class AgentRuntimeError(Exception):
    """Base exception for all agent runtime communication errors."""

    def __init__(self, message: str, detail: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class AgentRuntimeUnavailableError(AgentRuntimeError):
    """Raised when the agent-runtime service is unreachable (network error / connection refused)."""


class AgentRuntimeTimeoutError(AgentRuntimeError):
    """Raised when an operation against agent-runtime times out."""


class AgentRuntimeAuthenticationError(AgentRuntimeError):
    """Raised when internal service credentials are rejected (401/403)."""


class AgentRuntimeResponseError(AgentRuntimeError):
    """Raised when the agent runtime returns a non-2xx response."""

    def __init__(self, message: str, status_code: int, code: str = "RUNTIME_ERROR", detail: Any = None) -> None:
        super().__init__(message, detail=detail)
        self.status_code = status_code
        self.code = code


class AgentRuntimeMalformedResponseError(AgentRuntimeError):
    """Raised when the runtime response is unparseable or violates expected contract."""


# ---------------------------------------------------------------------------
# Client Implementation
# ---------------------------------------------------------------------------


class AgentRuntimeClient:
    """
    Thread-safe internal HTTP client for Django -> FastAPI Agent Runtime communication.
    """

    SERVICE_KEY_HEADER = "X-Internal-Service-Key"
    CORRELATION_ID_HEADER = "X-Correlation-Id"

    def __init__(
        self,
        base_url: Optional[str] = None,
        secret_key: Optional[str] = None,
        connect_timeout: Optional[float] = None,
        read_timeout: Optional[float] = None,
        write_timeout: Optional[float] = None,
        pool_timeout: Optional[float] = None,
    ) -> None:
        self.base_url = (base_url or getattr(settings, "AGENT_RUNTIME_URL", "http://agent-runtime:8001")).rstrip("/")
        self.secret_key = secret_key if secret_key is not None else getattr(settings, "INTERNAL_SERVICE_SECRET", "")
        self.connect_timeout = connect_timeout or getattr(settings, "AGENT_RUNTIME_CONNECT_TIMEOUT", 3.0)
        self.read_timeout = read_timeout or getattr(settings, "AGENT_RUNTIME_READ_TIMEOUT", 15.0)
        self.write_timeout = write_timeout or getattr(settings, "AGENT_RUNTIME_WRITE_TIMEOUT", 10.0)
        self.pool_timeout = pool_timeout or getattr(settings, "AGENT_RUNTIME_POOL_TIMEOUT", 5.0)

        # Reusable client session with bounded connection pooling
        self._client: Optional[httpx.Client] = None

    def _get_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            limits = httpx.Limits(
                max_keepalive_connections=20,
                max_connections=50,
                keepalive_expiry=30.0,
            )
            timeouts = httpx.Timeout(
                timeout=self.read_timeout,
                connect=self.connect_timeout,
                write=self.write_timeout,
                pool=self.pool_timeout,
            )
            self._client = httpx.Client(
                base_url=self.base_url,
                limits=limits,
                timeout=timeouts,
            )
        return self._client

    def _build_headers(self, custom_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {
            self.SERVICE_KEY_HEADER: self.secret_key,
            self.CORRELATION_ID_HEADER: get_correlation_id(),
            "Accept": "application/json",
            "User-Agent": "NEX-Django-Backend/1.0",
        }
        if custom_headers:
            headers.update(custom_headers)
        return headers

    def _sanitize_path(self, path: str) -> str:
        """Prevent arbitrary URL redirection and path traversal (SSRF protection)."""
        clean_path = path.strip()
        if "://" in clean_path or clean_path.startswith("//") or ".." in clean_path:
            raise ValueError(f"Illegal or SSRF-prone path rejected: '{path}'")
        if not clean_path.startswith("/"):
            raise ValueError(f"Runtime request path must start with '/': '{path}'")
        return clean_path

    def request(
        self,
        method: str,
        path: str,
        json_data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        custom_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Execute an HTTP request to the FastAPI Agent Runtime with error normalization and retries.
        """
        method_upper = method.upper()
        clean_path = self._sanitize_path(path)
        url = urljoin(f"{self.base_url}/", clean_path.lstrip("/"))
        headers = self._build_headers(custom_headers)
        client = self._get_client()

        # Idempotent methods (GET, HEAD) are allowed 1 retry on connection failure
        max_attempts = 2 if method_upper in ("GET", "HEAD") else 1
        last_exc: Optional[Exception] = None

        for attempt in range(1, max_attempts + 1):
            try:
                response = client.request(
                    method=method_upper,
                    url=clean_path,
                    json=json_data,
                    params=params,
                    headers=headers,
                )
                return self._handle_response(response, method_upper, clean_path)

            except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout) as exc:
                correlation_id = get_correlation_id()
                logger.error(
                    "Timeout communicating with Agent Runtime %s %s [correlation_id=%s]: %s",
                    method_upper,
                    clean_path,
                    correlation_id,
                    exc,
                )
                raise AgentRuntimeTimeoutError(
                    f"Agent runtime operation timed out on {method_upper} {clean_path}",
                    detail=str(exc),
                ) from exc

            except httpx.ConnectError as exc:
                last_exc = exc
                if attempt < max_attempts:
                    logger.warning(
                        "Transient connect error to Agent Runtime (%s %s). Retrying (attempt %d/%d)...",
                        method_upper,
                        clean_path,
                        attempt,
                        max_attempts,
                    )
                    time.sleep(0.1)
                    continue

                correlation_id = get_correlation_id()
                logger.error(
                    "Agent Runtime service unavailable on %s %s [correlation_id=%s]: %s",
                    method_upper,
                    clean_path,
                    correlation_id,
                    exc,
                )
                raise AgentRuntimeUnavailableError(
                    f"Agent runtime service unavailable on {method_upper} {clean_path}",
                    detail=str(exc),
                ) from exc

            except httpx.HTTPError as exc:
                correlation_id = get_correlation_id()
                logger.error(
                    "HTTP protocol error communicating with Agent Runtime %s %s [correlation_id=%s]: %s",
                    method_upper,
                    clean_path,
                    correlation_id,
                    exc,
                )
                raise AgentRuntimeUnavailableError(
                    f"HTTP error communicating with Agent Runtime: {str(exc)}",
                    detail=str(exc),
                ) from exc

        if last_exc:
            raise AgentRuntimeUnavailableError(f"Connection failed: {str(last_exc)}") from last_exc
        raise AgentRuntimeError("Request failed without response")

    def _handle_response(self, response: httpx.Response, method: str, path: str) -> Dict[str, Any]:
        """Validate and normalize HTTP responses from Agent Runtime."""
        correlation_id = get_correlation_id()

        # Parse JSON payload
        try:
            data = response.json() if response.content else {}
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error(
                "Malformed JSON response from Agent Runtime %s %s (status %d) [correlation_id=%s]",
                method,
                path,
                response.status_code,
                correlation_id,
            )
            raise AgentRuntimeMalformedResponseError(
                f"Agent runtime returned unparseable response (HTTP {response.status_code})",
                detail=response.text[:256] if hasattr(response, "text") else str(exc),
            ) from exc

        # Success path
        if 200 <= response.status_code < 300:
            return data

        # Authentication / Authorization rejection
        if response.status_code in (401, 403):
            logger.error(
                "Agent Runtime rejected internal service credentials on %s %s (HTTP %d) [correlation_id=%s]",
                method,
                path,
                response.status_code,
                correlation_id,
            )
            raise AgentRuntimeAuthenticationError(
                f"Agent runtime authentication failed (HTTP {response.status_code})",
                detail=data.get("error", {}).get("message") if isinstance(data, dict) else None,
            )

        # General error response handling
        error_info = data.get("error", {}) if isinstance(data, dict) else {}
        code = error_info.get("code", "RUNTIME_ERROR") if isinstance(error_info, dict) else "RUNTIME_ERROR"
        message = error_info.get("message", f"Runtime error HTTP {response.status_code}") if isinstance(error_info, dict) else str(data)
        detail = error_info.get("detail") if isinstance(error_info, dict) else None

        logger.warning(
            "Agent Runtime error %s (HTTP %d) on %s %s [correlation_id=%s]: %s",
            code,
            response.status_code,
            method,
            path,
            correlation_id,
            message,
        )
        raise AgentRuntimeResponseError(
            message=message,
            status_code=response.status_code,
            code=code,
            detail=detail,
        )

    # -----------------------------------------------------------------------
    # High-Level Typed Operations
    # -----------------------------------------------------------------------

    def ping(self, message: str = "ping") -> ServicePingResponseContract:
        """Test mutual service connectivity and credentials."""
        req = ServicePingRequestContract(message=message)
        res_data = self.request("POST", "/api/v1/ping", json_data=req.to_dict())
        return ServicePingResponseContract.from_dict(res_data)

    def get_status(self) -> Dict[str, Any]:
        """Fetch runtime operational status."""
        return self.request("GET", "/api/v1/status")

    def verify_task(self, task_id: str, action: str, parameters: Optional[Dict[str, Any]] = None) -> AgentTaskResponseContract:
        """Validate and dispatch a task contract to the agent runtime."""
        req = AgentTaskRequestContract(task_id=task_id, action=action, parameters=parameters or {})
        res_data = self.request("POST", "/api/v1/tasks/verify", json_data=req.to_dict())
        return AgentTaskResponseContract.from_dict(res_data)

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.request("GET", path, params=params)

    def post(self, path: str, json_data: Optional[Any] = None) -> Dict[str, Any]:
        return self.request("POST", path, json_data=json_data)

    def close(self) -> None:
        """Close client resources."""
        if self._client and not self._client.is_closed:
            self._client.close()
            self._client = None

    def __enter__(self) -> "AgentRuntimeClient":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()


# Module-level default client instance
runtime_client = AgentRuntimeClient()

