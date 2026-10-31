"""
NEX Agent Runtime — Middleware Components.

Implements:
  1. CorrelationIdMiddleware — Tracks X-Correlation-Id across async contexts,
     injects it into logging contextvars, and returns it in response headers.
  2. RequestBodyLimitMiddleware — Enforces maximum allowable request size on both
     stated Content-Length and actual streaming/chunked body bytes received (HTTP 413).
"""

import logging
import re
import time
import uuid
from typing import Any, Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.core.logging import correlation_id_ctx, get_correlation_id

logger = logging.getLogger("agent_runtime.middleware")

# Allowed characters: alphanumeric, hyphens, and underscores. Length: 1 to 64 chars.
_CORRELATION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")
CORRELATION_ID_HEADER = "X-Correlation-Id"
PROCESS_TIME_HEADER = "X-Process-Time-Ms"


def validate_or_generate_correlation_id(raw_id: str | None) -> str:
    """
    Validate an incoming correlation ID.
    If absent, empty, or failing sanity check, generate a clean UUIDv4 hex string.
    """
    if raw_id and _CORRELATION_ID_PATTERN.match(raw_id.strip()):
        return raw_id.strip()
    return uuid.uuid4().hex


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware to capture, validate, set in ContextVar, and propagate X-Correlation-Id.
    Also measures request latency and attaches X-Process-Time-Ms.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        incoming_id = request.headers.get(CORRELATION_ID_HEADER)
        correlation_id = validate_or_generate_correlation_id(incoming_id)

        token = correlation_id_ctx.set(correlation_id)
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

            response.headers[CORRELATION_ID_HEADER] = correlation_id
            response.headers[PROCESS_TIME_HEADER] = str(duration_ms)
            return response
        finally:
            correlation_id_ctx.reset(token)


class RequestBodyLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware enforcing maximum request body limits on both stated Content-Length
    and dynamically streamed/chunked request bodies.
    Protects against memory exhaustion attacks.
    """

    def __init__(self, app: Any, max_bytes: int = settings.max_request_body_size_bytes) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        # 1. Fast-path Content-Length header validation
        content_length_raw = request.headers.get("content-length")
        if content_length_raw:
            try:
                content_length = int(content_length_raw)
                if content_length > self.max_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": {
                                "code": "PAYLOAD_TOO_LARGE",
                                "message": f"Request body exceeds maximum allowed size of {self.max_bytes} bytes",
                                "detail": {"max_bytes": self.max_bytes, "received_bytes": content_length},
                            }
                        },
                    )
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": {
                            "code": "BAD_REQUEST",
                            "message": "Invalid Content-Length header",
                            "detail": None,
                        }
                    },
                )

        # 2. Dynamic stream chunk reader for chunked or missing Content-Length bodies
        total_bytes = 0
        chunks = []

        async for chunk in request.stream():
            total_bytes += len(chunk)
            if total_bytes > self.max_bytes:
                correlation_id = get_correlation_id()
                logger.warning(
                    "Streamed request body exceeded limit: received %d > max %d bytes [correlation_id=%s]",
                    total_bytes,
                    self.max_bytes,
                    correlation_id,
                )
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "code": "PAYLOAD_TOO_LARGE",
                            "message": f"Request body exceeds maximum allowed size of {self.max_bytes} bytes",
                            "detail": {"max_bytes": self.max_bytes, "received_bytes": total_bytes},
                        }
                    },
                )
            chunks.append(chunk)

        # Reconstruct cached body so downstream endpoint/Pydantic parsers can read it
        request._body = b"".join(chunks)

        return await call_next(request)
