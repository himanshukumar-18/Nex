"""
NEX Agent Runtime — Centralized Exception Handling & Standardized Error Envelopes.

Normalizes all API error responses into the consistent NEX format:
{
    "error": {
        "code": "ERROR_CODE",
        "message": "Human-readable error description",
        "detail": ...
    }
}
"""

import logging
from typing import Any
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core.logging import get_correlation_id

logger = logging.getLogger("agent_runtime.exceptions")


# ---------------------------------------------------------------------------
# Custom Domain Exceptions
# ---------------------------------------------------------------------------


class NexRuntimeError(Exception):
    """Base class for agent runtime domain exceptions."""

    def __init__(
        self,
        message: str,
        code: str = "RUNTIME_ERROR",
        status_code: int = 500,
        detail: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.detail = detail


class DependencyUnavailableError(NexRuntimeError):
    """Raised when an external dependency (Redis, Backend) cannot be reached."""

    def __init__(self, message: str = "Required service dependency is unavailable", detail: Any = None) -> None:
        super().__init__(
            message=message,
            code="SERVICE_UNAVAILABLE",
            status_code=503,
            detail=detail,
        )


class ResourceTimeoutError(NexRuntimeError):
    """Raised when an operation exceeds its configured timeout boundary."""

    def __init__(self, message: str = "Operation timed out", detail: Any = None) -> None:
        super().__init__(
            message=message,
            code="GATEWAY_TIMEOUT",
            status_code=504,
            detail=detail,
        )


class PayloadTooLargeError(BaseException):
    """Raised when the request body exceeds maximum allowable size limits."""

    def __init__(self, max_bytes: int, received_bytes: int) -> None:
        super().__init__(f"Request body exceeds maximum allowed size of {max_bytes} bytes")
        self.max_bytes = max_bytes
        self.received_bytes = received_bytes


# ---------------------------------------------------------------------------
# HTTP Status Code to Error Code Mapping
# ---------------------------------------------------------------------------

_STATUS_CODE_MAP = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    408: "REQUEST_TIMEOUT",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    422: "VALIDATION_ERROR",
    429: "TOO_MANY_REQUESTS",
    500: "INTERNAL_SERVER_ERROR",
    502: "BAD_GATEWAY",
    503: "SERVICE_UNAVAILABLE",
    504: "GATEWAY_TIMEOUT",
}


def create_error_response(
    status_code: int,
    code: str,
    message: str,
    detail: Any = None,
) -> JSONResponse:
    """Construct a standardized JSONResponse with NEX error envelope."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "detail": detail,
            }
        },
    )


# ---------------------------------------------------------------------------
# Exception Handlers
# ---------------------------------------------------------------------------


async def request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """
    Handle Pydantic request validation errors.
    Returns normalized 422 response with structured field error descriptions.
    """
    errors = []
    for err in exc.errors():
        field_loc = " -> ".join(str(loc) for loc in err.get("loc", []))
        errors.append({
            "field": field_loc,
            "message": err.get("msg", "Invalid value"),
            "type": err.get("type", "value_error"),
        })

    logger.warning(
        "Request validation error on %s %s: %s [correlation_id=%s]",
        request.method,
        request.url.path,
        errors,
        get_correlation_id(),
    )

    return create_error_response(
        status_code=422,
        code="VALIDATION_ERROR",
        message="Request input validation failed",
        detail=errors,
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """
    Handle Starlette / FastAPI HTTPExceptions.
    Normalizes status codes and standardizes error code envelope.
    """
    code = _STATUS_CODE_MAP.get(exc.status_code, "HTTP_ERROR")
    message = str(exc.detail) if exc.detail else "An HTTP error occurred"

    if exc.status_code >= 500:
        logger.error(
            "HTTP %d error on %s %s: %s [correlation_id=%s]",
            exc.status_code,
            request.method,
            request.url.path,
            message,
            get_correlation_id(),
        )
    else:
        logger.info(
            "Client error HTTP %d on %s %s: %s [correlation_id=%s]",
            exc.status_code,
            request.method,
            request.url.path,
            message,
            get_correlation_id(),
        )

    return create_error_response(
        status_code=exc.status_code,
        code=code,
        message=message,
        detail=None,
    )


async def nex_runtime_exception_handler(
    request: Request,
    exc: NexRuntimeError,
) -> JSONResponse:
    """Handle custom NexRuntimeError domain exceptions."""
    logger.error(
        "Runtime error %s on %s %s: %s [correlation_id=%s]",
        exc.code,
        request.method,
        request.url.path,
        exc.message,
        get_correlation_id(),
    )
    return create_error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        detail=exc.detail,
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """
    Handle unexpected/unhandled exceptions.
    Logs full exception with traceback and active correlation ID.
    Sanitizes response in production to prevent internal information leakage.
    """
    correlation_id = get_correlation_id()
    logger.exception(
        "Unhandled exception processing %s %s [correlation_id=%s]: %s",
        request.method,
        request.url.path,
        correlation_id,
        str(exc),
    )

    detail = str(exc) if settings.app_debug else None
    return create_error_response(
        status_code=500,
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected internal error occurred",
        detail=detail,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all centralized exception handlers on the FastAPI application."""
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(NexRuntimeError, nex_runtime_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(500, unhandled_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

