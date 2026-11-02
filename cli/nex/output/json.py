"""NEX Machine-Readable JSON Output Formatter.

Ensures strict separation:
- Valid JSON data emitted exclusively to stdout.
- Diagnostics, progress, and warnings routed to stderr.
"""

import json
import sys
from typing import Any

from nex.core.exceptions import NexError


def print_json_success(
    command: str,
    data: Any,
    correlation_id: str | None = None,
) -> None:
    """Emit a standard successful response envelope to stdout."""
    payload = {
        "status": "ok",
        "command": command,
        "correlation_id": correlation_id or "cli-local",
        "data": data,
    }
    sys.stdout.write(json.dumps(payload, indent=2, default=str) + "\n")
    sys.stdout.flush()


def print_json_error(
    command: str,
    error: Exception | NexError,
    correlation_id: str | None = None,
) -> None:
    """Emit a standard error envelope to stdout."""
    code = getattr(error, "code", "GENERAL_ERROR")
    message = getattr(error, "message", str(error))
    detail = getattr(error, "detail", None)
    suggestion = getattr(error, "suggestion", None)

    payload = {
        "status": "error",
        "command": command,
        "correlation_id": correlation_id or "cli-local",
        "error": {
            "code": code,
            "message": message,
            "detail": detail,
            "suggestion": suggestion,
        },
    }
    sys.stdout.write(json.dumps(payload, indent=2, default=str) + "\n")
    sys.stdout.flush()
