"""NEX Django Client Exceptions.

Normalizes HTTP exceptions from backend communication into typed domain errors.
"""

from typing import Any

from nex.core.exceptions import (
    NexAuthError,
    NexBackendUnavailableError,
    NexError,
)


class NexClientError(NexError):
    """Base exception for all HTTP client failures."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        detail: Any | None = None,
        code: str = "CLIENT_ERROR",
        suggestion: str | None = None,
    ) -> None:
        super().__init__(message, detail=detail, code=code, suggestion=suggestion)
        self.status_code = status_code


class NexClientNetworkError(NexBackendUnavailableError):
    """Raised when the backend network is unreachable or socket drops."""


class NexClientTimeoutError(NexBackendUnavailableError):
    """Raised when the backend request exceeds the timeout deadline."""


class NexClientAuthError(NexAuthError):
    """Raised when the backend rejects client credentials (HTTP 401/403)."""


class NexClientResponseError(NexClientError):
    """Raised when the backend returns a non-2xx error with a normalized error envelope."""


class NexClientMalformedResponseError(NexBackendUnavailableError):
    """Raised when the backend response is not valid JSON."""
