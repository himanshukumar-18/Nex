"""Automated unit and integration test suite for CLI GitHub authorization command."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from nex.core import credentials
from nex.core.exceptions import NexError
from nex.core.exit_codes import ExitCode
from nex.main import NexTyper, app
from typer.testing import CliRunner, Result


class NexCliRunner(CliRunner):
    """Custom test runner emulating NexTyper argument normalization and error handling."""

    def invoke(self, target_app: Any, args: Any = None, **kwargs: Any) -> Result:  # type: ignore[override]
        normalized = NexTyper._normalize_args(list(args or []))
        try:
            return super().invoke(target_app, normalized, catch_exceptions=False, **kwargs)
        except NexError as err:
            msg = f"✕ ERROR: {err.message}\n"
            return Result(
                runner=self,
                stdout_bytes=msg.encode(),
                stderr_bytes=b"",
                output_bytes=msg.encode(),
                return_value=None,
                exit_code=err.exit_code,
                exception=err,
            )


runner = NexCliRunner()


@pytest.fixture(autouse=True)
def clean_credentials_vault(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensure clean isolated credential vault for each test."""
    fake_fallback_dir = tmp_path / ".nex"
    fake_fallback_file = fake_fallback_dir / "credentials.json"
    monkeypatch.setattr(credentials, "FALLBACK_DIR", fake_fallback_dir)
    monkeypatch.setattr(credentials, "FALLBACK_FILE", fake_fallback_file)
    monkeypatch.delenv("NEX_API_KEY", raising=False)
    monkeypatch.delenv("NEX_CLI_TOKEN", raising=False)


def test_auth_github_unauthenticated() -> None:
    """Calling nex auth github without active session token raises AUTH_ERROR."""
    result = runner.invoke(app, ["auth", "github"])
    assert result.exit_code == ExitCode.AUTH_ERROR
    assert "NEX authentication required" in result.output


@patch("nex.commands.auth.NexDjangoClient")
def test_auth_github_not_connected(mock_client_class: MagicMock) -> None:
    """Calling nex auth github when no installations exist displays connect guidance."""
    credentials.save_credentials("test-session-token-1234")

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.request.return_value = {
        "configured": True,
        "app_slug": "nex-assistant",
        "connected": False,
        "installations_count": 0,
        "installations": [],
    }
    mock_client_class.return_value = mock_client

    result = runner.invoke(app, ["auth", "github"])
    assert result.exit_code == 0
    assert "GITHUB AUTHORIZATION: NOT CONNECTED" in result.output
    assert "nex auth github --connect" in result.output


@patch("nex.commands.auth.NexDjangoClient")
def test_auth_github_connected_table(mock_client_class: MagicMock) -> None:
    """Calling nex auth github when connected renders table of authorized accounts."""
    credentials.save_credentials("test-session-token-1234")

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.request.return_value = {
        "configured": True,
        "app_slug": "nex-assistant",
        "connected": True,
        "installations_count": 1,
        "installations": [
            {
                "account_login": "octocat-org",
                "account_type": "Organization",
                "installation_id": 998877,
                "target_type": "selected",
                "status": "active",
            }
        ],
    }
    mock_client_class.return_value = mock_client

    result = runner.invoke(app, ["auth", "github"])
    assert result.exit_code == 0
    assert "Authorized GitHub Installations" in result.output
    assert "octocat-org" in result.output
    assert "998877" in result.output


@patch("webbrowser.open")
@patch("nex.commands.auth.NexDjangoClient")
def test_auth_github_connect_flag(
    mock_client_class: MagicMock, mock_browser_open: MagicMock
) -> None:
    """Calling nex auth github --connect requests install URL and opens browser."""
    credentials.save_credentials("test-session-token-1234")

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.request.return_value = {
        "install_url": "https://github.com/apps/nex-assistant/installations/new?state=xyzStateToken",
        "state": "xyzStateToken",
    }
    mock_client_class.return_value = mock_client

    result = runner.invoke(app, ["auth", "github", "--connect"])
    assert result.exit_code == 0
    assert "Opening GitHub App installation in your default browser" in result.output
    mock_browser_open.assert_called_once_with(
        "https://github.com/apps/nex-assistant/installations/new?state=xyzStateToken"
    )


@patch("nex.commands.auth.NexDjangoClient")
def test_auth_github_json_output(mock_client_class: MagicMock) -> None:
    """Calling nex auth github --json returns valid JSON payload."""
    credentials.save_credentials("test-session-token-1234")

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.request.return_value = {
        "configured": True,
        "app_slug": "nex-assistant",
        "connected": True,
        "installations_count": 1,
        "installations": [],
    }
    mock_client_class.return_value = mock_client

    result = runner.invoke(app, ["auth", "github", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "ok"
    assert data["command"] == "auth.github"
    assert data["data"]["configured"] is True
