"""Automated unit and integration test suite for CLI repository commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
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
    monkeypatch.setattr(credentials, "_has_keyring_backend", lambda: False)
    monkeypatch.setattr(credentials, "FALLBACK_DIR", fake_fallback_dir)
    monkeypatch.setattr(credentials, "FALLBACK_FILE", fake_fallback_file)
    monkeypatch.delenv("NEX_API_KEY", raising=False)
    monkeypatch.delenv("NEX_CLI_TOKEN", raising=False)


def test_repos_list_unauthenticated() -> None:
    """Calling nex repos list without credentials fails with AUTH_ERROR."""
    result = runner.invoke(app, ["repos", "list"])
    assert result.exit_code == ExitCode.AUTH_ERROR
    assert "Not authenticated" in result.output


def test_repos_list_success() -> None:
    """Calling nex repos list returns formatted table of repositories."""
    credentials.save_credentials(access_token="valid_session_token_123")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.is_success = True
    mock_resp.content = b'{"count": 2}'
    mock_resp.json.return_value = {
        "count": 2,
        "results": [
            {
                "id": "c1f7b8b2-4d1a-4c2e-9d3a-123456789abc",
                "name": "ai-core",
                "full_name": "nex-org/ai-core",
                "is_private": True,
                "default_branch": "main",
                "language": "Python",
                "sync_status": "synced",
            },
            {
                "id": "e2f8c9d3-5e2b-5d3f-ae4b-987654321def",
                "name": "web-ui",
                "full_name": "nex-org/web-ui",
                "is_private": False,
                "default_branch": "development",
                "language": "TypeScript",
                "sync_status": "synced",
            },
        ],
    }

    with patch.object(httpx.Client, "request", return_value=mock_resp):
        result = runner.invoke(app, ["repos", "list"])

    assert result.exit_code == 0
    assert "nex-org/ai-core" in result.output
    assert "nex-org/web-ui" in result.output
    assert "PRIVATE" in result.output
    assert "PUBLIC" in result.output


def test_repos_list_empty() -> None:
    """Calling nex repos list with no repositories shows guidance message."""
    credentials.save_credentials(access_token="valid_session_token_123")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.is_success = True
    mock_resp.content = b'{"count": 0, "results": []}'
    mock_resp.json.return_value = {"count": 0, "results": []}

    with patch.object(httpx.Client, "request", return_value=mock_resp):
        result = runner.invoke(app, ["repos", "list"])

    assert result.exit_code == 0
    assert "No repositories found" in result.output
    assert "nex repos sync" in result.output


def test_repos_list_json() -> None:
    """Calling nex repos list --json outputs valid JSON structure."""
    credentials.save_credentials(access_token="valid_session_token_123")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.is_success = True
    mock_resp.content = b'{"count": 1}'
    mock_resp.json.return_value = {
        "count": 1,
        "results": [
            {
                "id": "c1f7b8b2-4d1a-4c2e-9d3a-123456789abc",
                "name": "ai-core",
                "full_name": "nex-org/ai-core",
                "is_private": True,
            }
        ],
    }

    with patch.object(httpx.Client, "request", return_value=mock_resp):
        result = runner.invoke(app, ["repos", "list", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "ok"
    assert data["command"] == "repos.list"
    assert data["data"]["count"] == 1


def test_repos_sync_success() -> None:
    """Calling nex repos sync triggers synchronization and displays metrics."""
    credentials.save_credentials(access_token="valid_session_token_123")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.is_success = True
    mock_resp.content = b'{"status": "completed"}'
    mock_resp.json.return_value = {
        "status": "completed",
        "total": 12,
        "added": 2,
        "updated": 10,
        "removed": 0,
        "installations_synced": 1,
        "synced_at": "2026-11-02T12:00:00Z",
    }

    with patch.object(httpx.Client, "request", return_value=mock_resp):
        result = runner.invoke(app, ["repos", "sync"])

    assert result.exit_code == 0
    assert "Repositories synchronized successfully" in result.output
    assert "12" in result.output
    assert "Added:" in result.output


def test_repos_sync_json() -> None:
    """Calling nex repos sync --json outputs structured JSON."""
    credentials.save_credentials(access_token="valid_session_token_123")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.is_success = True
    mock_resp.content = b'{"status": "completed"}'
    mock_resp.json.return_value = {
        "status": "completed",
        "total": 5,
        "added": 1,
        "updated": 4,
        "removed": 0,
        "installations_synced": 1,
    }

    with patch.object(httpx.Client, "request", return_value=mock_resp):
        result = runner.invoke(app, ["repos", "sync", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "ok"
    assert data["command"] == "repos.sync"
    assert data["data"]["total"] == 5


def test_repos_show_by_uuid() -> None:
    """Calling nex repos show with UUID displays repository panel."""
    credentials.save_credentials(access_token="valid_session_token_123")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.is_success = True
    mock_resp.content = b'{"id": "test"}'
    mock_resp.json.return_value = {
        "id": "c1f7b8b2-4d1a-4c2e-9d3a-123456789abc",
        "name": "ai-core",
        "full_name": "nex-org/ai-core",
        "description": "Production AI engine",
        "is_private": True,
        "default_branch": "main",
        "language": "Python",
        "clone_url": "https://github.com/nex-org/ai-core.git",
        "ssh_url": "git@github.com:nex-org/ai-core.git",
        "html_url": "https://github.com/nex-org/ai-core",
        "sync_status": "synced",
    }

    with patch.object(httpx.Client, "request", return_value=mock_resp):
        result = runner.invoke(app, ["repos", "show", "c1f7b8b2-4d1a-4c2e-9d3a-123456789abc"])

    assert result.exit_code == 0
    assert "nex-org/ai-core" in result.output
    assert "Production AI engine" in result.output
    assert "https://github.com/nex-org/ai-core.git" in result.output


def test_repos_show_by_name() -> None:
    """Calling nex repos show with repo slug resolves and displays repository panel."""
    credentials.save_credentials(access_token="valid_session_token_123")

    search_resp = MagicMock(spec=httpx.Response)
    search_resp.status_code = 200
    search_resp.is_success = True
    search_resp.content = b'{"results": []}'
    search_resp.json.return_value = {
        "results": [
            {
                "id": "c1f7b8b2-4d1a-4c2e-9d3a-123456789abc",
                "name": "ai-core",
                "full_name": "nex-org/ai-core",
                "github_repo_id": 998877,
            }
        ]
    }

    detail_resp = MagicMock(spec=httpx.Response)
    detail_resp.status_code = 200
    detail_resp.is_success = True
    detail_resp.content = b'{"id": "test"}'
    detail_resp.json.return_value = {
        "id": "c1f7b8b2-4d1a-4c2e-9d3a-123456789abc",
        "name": "ai-core",
        "full_name": "nex-org/ai-core",
        "description": "Production AI engine",
        "is_private": False,
        "default_branch": "main",
        "language": "Go",
        "clone_url": "https://github.com/nex-org/ai-core.git",
        "ssh_url": "git@github.com:nex-org/ai-core.git",
        "html_url": "https://github.com/nex-org/ai-core",
        "sync_status": "synced",
    }

    with patch.object(httpx.Client, "request", side_effect=[search_resp, detail_resp]):
        result = runner.invoke(app, ["repos", "show", "nex-org/ai-core"])

    assert result.exit_code == 0
    assert "nex-org/ai-core" in result.output
    assert "PUBLIC" in result.output


def test_repos_show_not_found() -> None:
    """Calling nex repos show with non-existent repo fails with NOT_FOUND."""
    credentials.save_credentials(access_token="valid_session_token_123")

    search_resp = MagicMock(spec=httpx.Response)
    search_resp.status_code = 200
    search_resp.is_success = True
    search_resp.content = b'{"results": []}'
    search_resp.json.return_value = {"results": []}

    with patch.object(httpx.Client, "request", return_value=search_resp):
        result = runner.invoke(app, ["repos", "show", "non-existent-repo"])

    assert result.exit_code == ExitCode.INVALID_INPUT
    assert "not found" in result.output.lower()
