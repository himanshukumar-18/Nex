"""
NEX Backend — Centralized API exception handling.

All Django REST Framework exceptions are normalized into a single, stable
response envelope:

    {
        "error": "<machine_readable_code>",
        "message": "<human_readable_summary>",
        "detail": <original_detail_or_null>
    }

Design decisions:
  - HTTP status codes are preserved from the original DRF exception.
  - Internal server errors (non-DRF exceptions) return HTTP 500 with a safe
    generic message. The actual exception is logged with a correlation ID so
    it can be traced in logs without exposing internals to the caller.
  - Validation errors are flattened into the `detail` field as a dict or list,
    keeping the machine-readable field-level structure DRF already provides.
  - Stack traces are NEVER returned to the client.
  - The `error` field is a stable snake_case code string suitable for
    programmatic handling in clients and CLI tools.

HTTP status → error code mapping:
  400 → validation_error
  401 → authentication_required
  403 → permission_denied
  404 → not_found
  405 → method_not_allowed
  406 → not_acceptable
  415 → unsupported_media_type
  429 → rate_limit_exceeded
  500 → internal_server_error
  (others) → api_error
"""

import logging
import uuid
from typing import TYPE_CHECKING, Any

from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    MethodNotAllowed,
    NotAuthenticated,
    NotFound,
    ParseError,
    PermissionDenied,
    Throttled,
    UnsupportedMediaType,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_default_handler

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stable error-code registry
# ---------------------------------------------------------------------------

_HTTP_STATUS_TO_ERROR_CODE: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "validation_error",
    status.HTTP_401_UNAUTHORIZED: "authentication_required",
    status.HTTP_403_FORBIDDEN: "permission_denied",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_405_METHOD_NOT_ALLOWED: "method_not_allowed",
    status.HTTP_406_NOT_ACCEPTABLE: "not_acceptable",
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: "unsupported_media_type",
    status.HTTP_429_TOO_MANY_REQUESTS: "rate_limit_exceeded",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "internal_server_error",
}

_HTTP_STATUS_TO_DEFAULT_MESSAGE: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "The request could not be understood due to invalid input.",
    status.HTTP_401_UNAUTHORIZED: "Authentication credentials are required.",
    status.HTTP_403_FORBIDDEN: "You do not have permission to perform this action.",
    status.HTTP_404_NOT_FOUND: "The requested resource was not found.",
    status.HTTP_405_METHOD_NOT_ALLOWED: "This HTTP method is not allowed for this endpoint.",
    status.HTTP_406_NOT_ACCEPTABLE: "The requested content type is not supported.",
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: "The submitted media type is not supported.",
    status.HTTP_429_TOO_MANY_REQUESTS: "Too many requests. Please slow down and try again later.",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "An internal error occurred. Please try again later.",
}


def _error_code_for_status(http_status: int) -> str:
    """Return the stable machine-readable error code for an HTTP status."""
    return _HTTP_STATUS_TO_ERROR_CODE.get(http_status, "api_error")


def _safe_message_for_exception(exc: APIException) -> str:
    """
    Return a human-readable message that is safe to expose to the client.

    For most exceptions the DRF default message is appropriate.
    For authentication failures we return a generic message to avoid
    leaking whether a user account exists.
    """
    if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
        return _HTTP_STATUS_TO_DEFAULT_MESSAGE[status.HTTP_401_UNAUTHORIZED]
    if isinstance(exc, Throttled):
        wait = exc.wait
        if wait is not None:
            return f"Too many requests. Please retry after {int(wait)} seconds."
        return _HTTP_STATUS_TO_DEFAULT_MESSAGE[status.HTTP_429_TOO_MANY_REQUESTS]
    return _HTTP_STATUS_TO_DEFAULT_MESSAGE.get(exc.status_code, str(exc.detail))


def _serialize_detail(detail: Any) -> Any:
    """
    Recursively convert DRF ErrorDetail objects into plain Python types
    so the response can be serialized as standard JSON.
    """
    if isinstance(detail, list):
        return [_serialize_detail(item) for item in detail]
    if isinstance(detail, dict):
        return {key: _serialize_detail(value) for key, value in detail.items()}
    return str(detail)


def nex_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """
    Central NEX API exception handler.

    Normalizes all DRF exceptions and unhandled Django exceptions into the
    standard NEX error envelope. Logs unexpected internal server errors with
    a correlation ID without exposing any details to the caller.

    Return None for exceptions that DRF cannot handle (Django will then
    return its own error response — this should not occur behind DRF views).
    """
    # Convert Django Http404 to DRF NotFound so it gets consistent treatment
    if isinstance(exc, Http404):
        exc = NotFound()

    # Let DRF process the exception first (runs authentication handlers etc.)
    response = drf_default_handler(exc, context)

    if response is None:
        # Unhandled exception — reuse request correlation ID if available,
        # otherwise generate a new one for log tracing.
        request = context.get("request") if isinstance(context, dict) else None
        correlation_id = getattr(request, "correlation_id", None) or str(uuid.uuid4())
        logger.exception(
            "Unhandled exception in API view",
            extra={"correlation_id": correlation_id},
        )
        return Response(
            {
                "error": "internal_server_error",
                "message": _HTTP_STATUS_TO_DEFAULT_MESSAGE[
                    status.HTTP_500_INTERNAL_SERVER_ERROR
                ],
                "correlation_id": correlation_id,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if not isinstance(exc, APIException):
        return response

    http_status: int = response.status_code
    error_code = _error_code_for_status(http_status)
    message = _safe_message_for_exception(exc)

    # For validation errors, preserve the structured field-level detail.
    # For all other errors, detail is a simple string or None.
    if isinstance(exc, (ValidationError, ParseError)):
        detail: Any = _serialize_detail(exc.detail)
    else:
        detail = None

    response.data = {
        "error": error_code,
        "message": message,
        "detail": detail,
    }

    # Propagate Retry-After header from Throttled exceptions
    if isinstance(exc, Throttled) and exc.wait is not None:
        response["Retry-After"] = str(int(exc.wait))

    return response
