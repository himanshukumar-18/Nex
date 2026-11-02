"""Tests for terminal styling and JSON output formatters."""

import io
import json
import sys

import pytest
from nex.core.exceptions import NexInvalidInputError
from nex.output.json import print_json_error, print_json_success
from nex.output.terminal import TerminalOutput


def test_print_json_success_format(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure print_json_success outputs valid JSON envelope to stdout."""
    stdout_buf = io.StringIO()
    monkeypatch.setattr(sys.stdout, "write", stdout_buf.write)
    monkeypatch.setattr(sys.stdout, "flush", lambda: None)

    print_json_success("test_cmd", {"key": "value"}, "correlation-123")

    output_str = stdout_buf.getvalue()
    data = json.loads(output_str)

    assert data["status"] == "ok"
    assert data["command"] == "test_cmd"
    assert data["correlation_id"] == "correlation-123"
    assert data["data"] == {"key": "value"}


def test_print_json_error_format(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure print_json_error outputs valid error envelope to stdout."""
    stdout_buf = io.StringIO()
    monkeypatch.setattr(sys.stdout, "write", stdout_buf.write)
    monkeypatch.setattr(sys.stdout, "flush", lambda: None)

    err = NexInvalidInputError(
        "Invalid flag", detail="Extra info", suggestion="Try again"
    )
    print_json_error("bad_cmd", err, "correlation-456")

    output_str = stdout_buf.getvalue()
    data = json.loads(output_str)

    assert data["status"] == "error"
    assert data["command"] == "bad_cmd"
    assert data["correlation_id"] == "correlation-456"
    assert data["error"]["code"] == "INVALID_INPUT"
    assert data["error"]["message"] == "Invalid flag"
    assert data["error"]["detail"] == "Extra info"
    assert data["error"]["suggestion"] == "Try again"


def test_terminal_output_renders_without_crashing() -> None:
    """Ensure TerminalOutput methods execute smoothly."""
    out = TerminalOutput(is_verbose=True, no_color=True)
    out.print_banner("Test Banner", "Subtitle")
    out.print_success("Operation completed")
    out.print_info("Informational message")
    out.print_warning("Warning notice")
    out.print_error("Failed action", "Review logs")
    out.print_verbose("Verbose diagnostics")
    out.print_table("Sample Table", ["Col A", "Col B"], [["1", "2"]])
    out.print_key_value_pairs("Properties", [("Key", "Value")])
