"""
NEX Agent Runtime — Structured JSON Logging & Correlation Tracking.

All log output is formatted as single-line JSON on stdout.
Correlation IDs from incoming requests are injected automatically into every
log line via ContextVar. Sensitive credentials (tokens, passwords) are scrubbed.
"""

from contextvars import ContextVar
import datetime
import json
import logging
import re
import sys
from typing import Any

# ContextVar storing the current request correlation ID across async tasks
correlation_id_ctx: ContextVar[str | None] = ContextVar("correlation_id_ctx", default=None)


def get_correlation_id() -> str:
    """Return the active correlation ID or '-' if unset."""
    cid = correlation_id_ctx.get()
    return cid if cid else "-"


class CorrelationIdFilter(logging.Filter):
    """Logging filter that attaches the active correlation ID to every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id()  # type: ignore[attr-defined]
        return True


# Sensitive token scrubbing patterns
_SENSITIVE_PATTERNS = [
    re.compile(r"(password[:=]\s*)[^\s,;&'\"]+", re.IGNORECASE),
    re.compile(r"(secret[:=]\s*)[^\s,;&'\"]+", re.IGNORECASE),
    re.compile(r"(token[:=]\s*)[^\s,;&'\"]+", re.IGNORECASE),
    re.compile(r"(authorization[:=]\s*(?:bearer\s+)?)[^\s,;&'\"]+", re.IGNORECASE),
    re.compile(r"(redis://[^:]+:)[^@]+(@)", re.IGNORECASE),
]


def scrub_sensitive_data(message: str) -> str:
    """Mask credential patterns in log messages."""
    for pattern in _SENSITIVE_PATTERNS:
        if "redis://" in pattern.pattern:
            message = pattern.sub(r"\1***\2", message)
        else:
            message = pattern.sub(r"\1***", message)
    return message


class JSONLogFormatter(logging.Formatter):
    """
    Structured JSON formatter for stdout logging.
    Emits consistent JSON dictionaries per log line.
    """

    def __init__(self, app_env: str = "development") -> None:
        super().__init__()
        self.app_env = app_env

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": scrub_sensitive_data(record.getMessage()),
            "correlation_id": getattr(record, "correlation_id", get_correlation_id()),
            "environment": self.app_env,
        }

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def setup_logging(log_level: str = "INFO", app_env: str = "development") -> None:
    """Initialize structured JSON logging for the agent runtime application."""
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())

    # Remove existing handlers to avoid duplicates
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level.upper())
    handler.addFilter(CorrelationIdFilter())
    handler.setFormatter(JSONLogFormatter(app_env=app_env))

    root_logger.addHandler(handler)

    # Silence overly verbose third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

