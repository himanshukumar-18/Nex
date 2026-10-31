"""
NEX Backend — Request correlation ID middleware.

Assigns a UUID4 correlation ID to every incoming HTTP request.

Purpose:
  - Links all log entries produced during a single request cycle,
    including logs from views, services, and exception handlers.
  - Enables efficient log-based debugging and incident tracing across
    multiple workers without a distributed tracing system.
  - Exposes the correlation ID in response headers so clients (API
    consumers, CLI tools) can submit it when reporting issues.

Behaviour:
  1. Checks the incoming request for an X-Correlation-Id header.
     If present and a valid UUID4, it is reused (allows request
     tracing to span service boundaries when trusted callers set it).
     Unknown or malformed values are silently replaced.
  2. A new UUID4 is generated if no valid ID is provided.
  3. The ID is attached to the request object as `request.correlation_id`.
  4. All log records produced during the request cycle include the ID
     via the CorrelationIdFilter log filter.
  5. The ID is returned to the client in the X-Correlation-Id response header.

Security:
  - Incoming X-Correlation-Id values are validated to be valid UUID4 strings.
    Invalid values are replaced silently — they are not logged or echoed back.
  - The correlation ID is a diagnostic tool only. It is not a security token
    and must never be used for authentication or authorization.
  - Correlation IDs are not logged at the start of every request to avoid
    exposing request metadata in high-volume logs. They are included in
    exception and security event logs only.

Usage in views and services:
  correlation_id = getattr(request, "correlation_id", "unknown")

Usage in log filter (configured in settings.LOGGING):
  "filters": {
      "correlation_id": {
          "()": "apps.api.middleware.CorrelationIdFilter",
      }
  }
"""

import contextvars
import logging
import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)

CORRELATION_ID_HEADER = "X-Correlation-Id"
CORRELATION_ID_META_KEY = "HTTP_X_CORRELATION_ID"

# Context variable preserving the current request's correlation ID across the execution call stack
_current_correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "current_correlation_id", default="no-request"
)
correlation_id_ctx = _current_correlation_id


def get_current_correlation_id() -> str:
    """Return the active request's correlation ID, or 'no-request' if outside a request cycle."""
    return _current_correlation_id.get()


get_correlation_id = get_current_correlation_id


def _generate_correlation_id() -> str:
    """Generate a new UUID4 correlation ID string."""
    return str(uuid.uuid4())


def _is_valid_uuid4(value: str) -> bool:
    """
    Return True if the value is a valid UUID4 string, False otherwise.

    Enforces an explicit length check (36 characters) to discard oversized
    payloads immediately without allocating memory for parsing.
    """
    if not isinstance(value, str) or len(value) != 36:
        return False
    try:
        parsed = uuid.UUID(value, version=4)
        return str(parsed) == value.lower()
    except (ValueError, AttributeError):
        return False


class CorrelationIdMiddleware:
    """
    WSGI middleware that attaches a correlation ID to every HTTP request.

    Designed to be used as a standard Django middleware in MIDDLEWARE setting.
    Place it early in the stack so that exception handlers and downstream
    middleware can access request.correlation_id.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        correlation_id = self._resolve_correlation_id(request)
        request.correlation_id = correlation_id  # type: ignore[attr-defined]

        # Bind correlation ID to context variable for structured logging
        token = _current_correlation_id.set(correlation_id)
        try:
            response = self.get_response(request)
            response[CORRELATION_ID_HEADER] = correlation_id
            return response
        finally:
            _current_correlation_id.reset(token)

    def _resolve_correlation_id(self, request: HttpRequest) -> str:
        """
        Extract a valid correlation ID from the request headers, or generate one.

        Incoming values are validated strictly. Malformed values are replaced
        without logging to prevent log injection through crafted headers.
        """
        incoming = request.META.get(CORRELATION_ID_META_KEY, "")
        if incoming and _is_valid_uuid4(incoming):
            return incoming.lower()
        return _generate_correlation_id()


class CorrelationIdFilter(logging.Filter):
    """
    Python logging filter that injects the request correlation ID into log records.

    Configure in settings.LOGGING:

        "filters": {
            "add_correlation_id": {
                "()": "apps.api.middleware.CorrelationIdFilter",
            }
        }

    Log records will automatically include the correlation ID from contextvars.
    If no correlation ID is available (e.g. management commands),
    the attribute is set to 'no-request'.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "correlation_id") or record.correlation_id == "no-request":
            record.correlation_id = _current_correlation_id.get()  # type: ignore[attr-defined]
        return True

