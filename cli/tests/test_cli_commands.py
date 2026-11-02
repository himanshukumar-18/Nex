"""Integration tests for all NEX CLI commands and workflows."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

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


def test_cli_help() -> None:
    """Ensure nex --help displays commands and exits 0."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Autonomous Intelligence for Software Engineering" in result.output
    assert "init" in result.output
    assert "inspect" in result.output
    assert "review" in result.output
    assert "fix" in result.output
    assert "test" in result.output
    assert "security" in result.output
    assert "pr" in result.output
    assert "config" in result.output
    assert "runs" in result.output


def test_cli_version() -> None:
    """Ensure nex --version reports version."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_cli_version_json() -> None:
    """Ensure nex --version --json outputs valid JSON."""
    result = runner.invoke(app, ["--version", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "ok"
    assert data["data"]["version"] == "0.1.0"


def test_cli_init_command(tmp_path: Path) -> None:
    """Test nex init creates .nex/config.toml in target repository."""
    result = runner.invoke(
        app, ["init", "--path", str(tmp_path), "--name", "test-project"]
    )
    assert result.exit_code == 0
    config_file = tmp_path / ".nex" / "config.toml"
    assert config_file.exists()


def test_cli_inspect_command() -> None:
    """Test nex inspect returns repository summary."""
    result = runner.invoke(app, ["inspect"])
    assert result.exit_code == 0
    assert "REPOSITORY INSPECTION" in result.output
    assert "WORKSPACE METADATA" in result.output


def test_cli_inspect_json_command() -> None:
    """Test nex inspect --json outputs valid json payload."""
    result = runner.invoke(app, ["inspect", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "ok"
    assert "repository" in data["data"]
    assert "git" in data["data"]


def test_cli_review_command() -> None:
    """Test nex review and nex review --staged."""
    res1 = runner.invoke(app, ["review"])
    assert res1.exit_code == 0
    assert "CODE REVIEW" in res1.output

    res2 = runner.invoke(app, ["review", "--staged"])
    assert res2.exit_code == 0
    assert "CODE REVIEW" in res2.output


def test_cli_fix_dry_run() -> None:
    """Test nex fix <issue> with --dry-run completes safely without modifying code."""
    result = runner.invoke(app, ["fix", "Fix null pointer in auth", "--dry-run"])
    assert result.exit_code == 0
    assert "ISSUE FIX PLAN (DRY-RUN)" in result.output
    assert "Dry-run preview completed" in result.output


def test_cli_fix_yes_flag_policy_violation() -> None:
    """Test nex fix with --yes raises policy violation exit code 7."""
    result = runner.invoke(app, ["fix", "Fix bug", "--yes"])
    assert result.exit_code == ExitCode.POLICY_VIOLATION
    assert "cannot bypass approval for HIGH-risk operation" in result.output


def test_cli_test_default_sandbox_policy() -> None:
    """Test nex test routes to isolated sandbox by default."""
    result = runner.invoke(app, ["test"])
    assert result.exit_code == 0
    assert "VERIFICATION & TEST EXECUTION" in result.output
    assert "ISOLATED SANDBOX (DEFAULT)" in result.output


def test_cli_test_local_yes_flag_policy_violation() -> None:
    """Test nex test --local --yes raises policy violation exit code 7."""
    result = runner.invoke(app, ["test", "--local", "--yes"])
    assert result.exit_code == ExitCode.POLICY_VIOLATION
    assert "cannot bypass approval for HIGH-risk operation" in result.output


def test_cli_security_command() -> None:
    """Test nex security scans repository for credentials."""
    result = runner.invoke(app, ["security"])
    assert result.exit_code == 0
    assert "SECURITY & CREDENTIAL AUDIT" in result.output


def test_cli_security_clean_directory(tmp_path: Path) -> None:
    """Test nex security on clean directory passes."""
    clean_dir = tmp_path / "clean_repo"
    clean_dir.mkdir()
    (clean_dir / "app.py").write_text("print('clean')")

    result = runner.invoke(app, ["security", "--path", str(clean_dir)])
    assert result.exit_code == 0
    assert "Security scan passed" in result.output


def test_cli_pr_yes_flag_policy_violation() -> None:
    """Test nex pr with --yes raises policy violation exit code 7."""
    result = runner.invoke(app, ["pr", "--yes"])
    assert result.exit_code == ExitCode.POLICY_VIOLATION
    assert "cannot bypass approval for CRITICAL-risk operation" in result.output


def test_cli_config_commands(tmp_path: Path) -> None:
    """Test nex config show, path, get, and set."""
    repo = tmp_path / "config_repo"
    repo.mkdir()

    # Initialize project config
    runner.invoke(app, ["init", "--path", str(repo), "--name", "cfg-test"])

    # config show
    res_show = runner.invoke(app, ["config", "show", "--path", str(repo)])
    assert res_show.exit_code == 0
    assert "ACTIVE CONFIGURATION" in res_show.output

    # config path
    res_path = runner.invoke(app, ["config", "path", "--path", str(repo)])
    assert res_path.exit_code == 0
    assert "CONFIGURATION PATHS" in res_path.output

    # config get
    res_get = runner.invoke(
        app, ["config", "get", "general.default_model", "--path", str(repo)]
    )
    assert res_get.exit_code == 0
    assert "gemini-2.0-flash" in res_get.output

    # config set
    res_set = runner.invoke(
        app,
        [
            "config",
            "set",
            "general.default_model",
            "custom-model-v1",
            "--path",
            str(repo),
        ],
    )
    assert res_set.exit_code == 0
    assert "Updated 'general.default_model' = custom-model-v1" in res_set.output

    # Verify set updated value
    res_get2 = runner.invoke(
        app, ["config", "get", "general.default_model", "--path", str(repo)]
    )
    assert res_get2.exit_code == 0
    assert "custom-model-v1" in res_get2.output


def test_cli_runs_list_backend_handling() -> None:
    """Test nex runs list displays clean status when endpoint is pending or empty."""
    with patch("nex.client.django.NexDjangoClient.get_runs", return_value=[]):
        result = runner.invoke(app, ["runs", "list"])
        assert result.exit_code == 0
        assert "AGENT TASK RUNS" in result.output
