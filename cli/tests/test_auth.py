"""NEX CLI — Tests for Authentication, Keyring Storage, and PKCE Flow."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from nex.commands.login import CallbackResult, make_handler
from nex.core import credentials
from nex.core.exceptions import NexError
from nex.core.exit_codes import ExitCode
from nex.main import NexTyper, app
from typer.testing import CliRunner, Result


class NexCliRunner(CliRunner):
    """Custom test runner emulating NexTyper argument normalization and error handling."""

    def invoke(self, app: Any, args: Any = None, **kwargs: Any) -> Result:  # type: ignore[override]
        normalized = NexTyper._normalize_args(list(args or []))
        try:
            return super().invoke(app, normalized, catch_exceptions=False, **kwargs)
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
    """Ensure a clean, isolated credential store for each test."""
    fake_fallback_dir = tmp_path / ".nex"
    fake_fallback_file = fake_fallback_dir / "credentials.json"
    monkeypatch.setattr(credentials, "FALLBACK_DIR", fake_fallback_dir)
    monkeypatch.setattr(credentials, "FALLBACK_FILE", fake_fallback_file)
    monkeypatch.delenv("NEX_API_KEY", raising=False)
    monkeypatch.delenv("NEX_CLI_TOKEN", raising=False)

    # Mock OS keyring backend to use fallback file cleanly in test runner
    monkeypatch.setattr(credentials, "_has_keyring_backend", lambda: False)
    credentials.clear_credentials()


class TestCredentialsVault:
    """Test suite for credential storage operations."""

    def test_save_and_retrieve_token(self) -> None:
        credentials.save_credentials(
            "nex_cli_test_token_123",
            user_info={"email": "alex@nex.dev", "role": "developer"},
        )

        assert credentials.get_stored_token() == "nex_cli_test_token_123"
        user = credentials.get_stored_user()
        assert user is not None
        assert user["email"] == "alex@nex.dev"
        assert user["role"] == "developer"

    def test_clear_credentials(self) -> None:
        credentials.save_credentials("nex_cli_temp_token")
        assert credentials.get_stored_token() == "nex_cli_temp_token"

        credentials.clear_credentials()
        assert credentials.get_stored_token() is None
        assert credentials.get_stored_user() is None

    def test_env_var_override_takes_precedence(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        credentials.save_credentials("stored_token")
        monkeypatch.setenv("NEX_API_KEY", "override_token_env")

        assert credentials.get_stored_token() == "override_token_env"


class TestAuthCommands:
    """Test suite for nex auth, whoami, and logout CLI commands."""

    def test_auth_status_unauthenticated(self) -> None:
        result = runner.invoke(app, ["auth", "status"])
        assert result.exit_code == 0
        assert "NOT AUTHENTICATED" in result.stdout

    def test_auth_status_unauthenticated_json(self) -> None:
        result = runner.invoke(app, ["--json", "auth", "status"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        assert data["data"]["authenticated"] is False

    @patch("nex.commands.auth.NexDjangoClient")
    def test_auth_status_authenticated(self, mock_client_cls: MagicMock) -> None:
        credentials.save_credentials("valid_token")

        mock_instance = MagicMock()
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.request.return_value = {
            "email": "developer@nex.dev",
            "display_name": "Dev Alex",
            "role": "developer",
            "email_verified": True,
        }
        mock_client_cls.return_value = mock_instance

        result = runner.invoke(app, ["auth", "status"])
        assert result.exit_code == 0
        assert "ACTIVE" in result.stdout
        assert "developer@nex.dev" in result.stdout

    def test_whoami_unauthenticated_fails(self) -> None:
        result = runner.invoke(app, ["whoami"])
        assert result.exit_code == ExitCode.AUTH_ERROR
        assert "Not authenticated" in result.stdout

    @patch("nex.commands.auth.NexDjangoClient")
    def test_whoami_authenticated(self, mock_client_cls: MagicMock) -> None:
        credentials.save_credentials("valid_token")

        mock_instance = MagicMock()
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.request.return_value = {
            "email": "alex@nex.dev",
            "role": "developer",
        }
        mock_client_cls.return_value = mock_instance

        result = runner.invoke(app, ["whoami"])
        assert result.exit_code == 0
        assert "alex@nex.dev" in result.stdout
        assert "developer" in result.stdout

    @patch("nex.commands.auth.NexDjangoClient")
    def test_logout_clears_credentials_and_revokes(
        self, mock_client_cls: MagicMock
    ) -> None:
        credentials.save_credentials("token_to_revoke")

        mock_instance = MagicMock()
        mock_instance.__enter__.return_value = mock_instance
        mock_client_cls.return_value = mock_instance

        result = runner.invoke(app, ["logout"])
        assert result.exit_code == 0
        assert "Logged out successfully" in result.stdout
        assert credentials.get_stored_token() is None

        mock_instance.request.assert_called_once_with("POST", "/auth/cli/revoke/")


class TestLoopbackHandler:
    """Test suite for the ephemeral loopback callback handler."""

    def test_handler_records_code_and_state(self) -> None:
        result = CallbackResult()
        handler_cls = make_handler("valid_state_123", result)

        mock_request = MagicMock()
        mock_request.makefile.return_value.readline.side_effect = [
            b"GET /callback?code=received_auth_code_xyz&state=valid_state_123 HTTP/1.1\r\n",
            b"Host: 127.0.0.1\r\n",
            b"\r\n",
        ]

        server_address = ("127.0.0.1", 8942)
        mock_server = MagicMock()
        mock_server.server_address = server_address

        handler_cls(mock_request, ("127.0.0.1", 54321), mock_server)
        assert result.code == "received_auth_code_xyz"
        assert result.state == "valid_state_123"
        assert result.error is None

    def test_handler_rejects_state_mismatch(self) -> None:
        result = CallbackResult()
        handler_cls = make_handler("expected_state_abc", result)

        mock_request = MagicMock()
        mock_request.makefile.return_value.readline.side_effect = [
            b"GET /callback?code=some_code&state=wrong_state_xyz HTTP/1.1\r\n",
            b"Host: 127.0.0.1\r\n",
            b"\r\n",
        ]

        mock_server = MagicMock()
        mock_server.server_address = ("127.0.0.1", 8942)

        handler_cls(mock_request, ("127.0.0.1", 54321), mock_server)
        assert result.code is None
        assert "State mismatch" in (result.error or "")

    def test_handler_handles_error_param(self) -> None:
        result = CallbackResult()
        handler_cls = make_handler("expected_state_abc", result)

        mock_request = MagicMock()
        mock_request.makefile.return_value.readline.side_effect = [
            b"GET /callback?error=access_denied&state=expected_state_abc HTTP/1.1\r\n",
            b"Host: 127.0.0.1\r\n",
            b"\r\n",
        ]

        mock_server = MagicMock()
        mock_server.server_address = ("127.0.0.1", 8942)

        handler_cls(mock_request, ("127.0.0.1", 54321), mock_server)
        assert result.error == "access_denied"
