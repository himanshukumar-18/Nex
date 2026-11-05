"""NEX CLI Pull Request (PR) Command Integration Tests.

Validates:
- Detached HEAD rejection
- Anti-silent-push verification (remote branch existence & unpushed commit checks)
- Base vs head branch divergence enforcement
- Dry-run comparison preview without remote publishing
- Strict CRITICAL-risk approval boundary (--yes blocked)
- Pull request creation and rich terminal output
- Machine-readable JSON output
- Subcommands: nex pr list and nex pr view
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from nex.core.exceptions import NexError
from nex.core.exit_codes import ExitCode
from nex.main import NexTyper, app
from typer.testing import CliRunner, Result


class NexCliRunner:
    """Helper runner emulating Typer argument hoisting and domain exception handling."""

    def invoke(self, cli_app: Any, args: list[str], input: str | None = None) -> Result:
        raw_runner = CliRunner()
        normalized = NexTyper._normalize_args(list(args))
        try:
            return raw_runner.invoke(cli_app, normalized, input=input, catch_exceptions=False)
        except NexError as err:
            msg = f"✕ ERROR: {err.message}\n"
            if err.suggestion:
                msg += f"  → Suggestion: {err.suggestion}\n"
            return Result(
                runner=raw_runner,
                stdout_bytes=msg.encode(),
                stderr_bytes=b"",
                output_bytes=msg.encode(),
                return_value=None,
                exit_code=err.exit_code,
                exception=err,
            )


runner = NexCliRunner()


@pytest.fixture
def git_repo_with_remote(tmp_path: Path) -> Path:
    """Create a temporary git repository with a simulated origin remote and pushed branch."""
    repo = tmp_path / "test_repo"
    repo.mkdir()

    # Init repo
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@nex.dev"], cwd=repo, check=True, capture_output=True)

    # Initial commit on main
    (repo / "README.md").write_text("# Test Repo\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo, check=True, capture_output=True)

    # Create a feature branch
    subprocess.run(["git", "checkout", "-b", "feature/my-feat"], cwd=repo, check=True, capture_output=True)
    (repo / "feature.py").write_text("print('feature')\n")
    subprocess.run(["git", "add", "feature.py"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Add feature logic"], cwd=repo, check=True, capture_output=True)

    # Simulate origin remote and remote-tracking refs
    subprocess.run(["git", "remote", "add", "origin", "https://github.com/test-org/test-repo.git"], cwd=repo, check=True, capture_output=True)

    # Create fake remote ref refs/remotes/origin/feature/my-feat pointing to HEAD
    head_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()
    subprocess.run(["git", "update-ref", "refs/remotes/origin/feature/my-feat", head_sha], cwd=repo, check=True, capture_output=True)

    return repo


MOCK_REPO_DATA = {
    "id": "11111111-2222-3333-4444-555555555555",
    "name": "test-repo",
    "full_name": "test-org/test-repo",
    "default_branch": "main",
    "is_private": False,
    "sync_status": "synced",
}

MOCK_PREVIEW_DATA = {
    "preview_fingerprint": "abc123sha256fingerprint",
    "base": "main",
    "head": "feature/my-feat",
    "commits": [
        {"sha": "c0ffee1", "message": "Add feature logic", "author": "Test User"}
    ],
    "changed_files": [
        {"filename": "feature.py", "status": "added", "additions": 1, "deletions": 0}
    ],
    "additions": 1,
    "deletions": 0,
    "has_conflicts": False,
    "suggested_title": "Add feature logic",
    "suggested_body": "Automated description based on commits.",
}

MOCK_CREATED_PR = {
    "id": "99999999-8888-7777-6666-555555555555",
    "number": 42,
    "title": "Add feature logic",
    "body": "Automated description based on commits.",
    "state": "open",
    "draft": False,
    "head_branch": "feature/my-feat",
    "base_branch": "main",
    "html_url": "https://github.com/test-org/test-repo/pull/42",
    "author_username": "test-user",
    "created_at": "2026-11-03T18:00:00Z",
    "updated_at": "2026-11-03T18:00:00Z",
}


def test_pr_requires_auth(git_repo_with_remote: Path) -> None:
    """Test nex pr fails with AUTH_ERROR when unauthenticated."""
    with patch("nex.commands.pr.get_stored_token", return_value=None):
        result = runner.invoke(app, ["pr", "--path", str(git_repo_with_remote)])
        assert result.exit_code == ExitCode.AUTH_ERROR
        assert "Not authenticated" in result.output


def test_pr_yes_flag_forbidden(git_repo_with_remote: Path) -> None:
    """Test nex pr with --yes raises policy violation exit code 7."""
    with patch("nex.commands.pr.get_stored_token", return_value="fake-token"):
        result = runner.invoke(app, ["pr", "--yes", "--path", str(git_repo_with_remote)])
        assert result.exit_code == ExitCode.POLICY_VIOLATION
        assert "cannot bypass approval for CRITICAL-risk operation" in result.output


def test_pr_detached_head_rejected(tmp_path: Path) -> None:
    """Test nex pr rejects detached HEAD repositories."""
    repo = tmp_path / "detached_repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@nex.dev"], cwd=repo, check=True, capture_output=True)
    (repo / "file.txt").write_text("hello")
    subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "checkout", "--detach"], cwd=repo, check=True, capture_output=True)

    with patch("nex.commands.pr.get_stored_token", return_value="fake-token"):
        result = runner.invoke(app, ["pr", "--path", str(repo)])
        assert result.exit_code != 0
        assert "Cannot create a pull request while HEAD is detached" in result.output


def test_pr_same_branch_rejected(git_repo_with_remote: Path) -> None:
    """Test nex pr rejects creating PR when head branch matches base branch."""
    with patch("nex.commands.pr.get_stored_token", return_value="fake-token"):
        with patch("nex.commands.pr._resolve_repo", return_value=MOCK_REPO_DATA):
            result = runner.invoke(
                app,
                ["pr", "--head", "main", "--base", "main", "--path", str(git_repo_with_remote)],
            )
            assert result.exit_code == ExitCode.POLICY_VIOLATION
            assert "cannot be the same as base branch" in result.output


def test_pr_unpushed_branch_rejected(tmp_path: Path) -> None:
    """Test nex pr rejects branch that has never been pushed to remote."""
    repo = tmp_path / "unpushed_repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "feature/unpushed"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@nex.dev"], cwd=repo, check=True, capture_output=True)
    (repo / "file.txt").write_text("unpushed")
    subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Commit on feature"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", "https://github.com/test-org/test-repo.git"], cwd=repo, check=True, capture_output=True)

    with patch("nex.commands.pr.get_stored_token", return_value="fake-token"):
        with patch("nex.commands.pr._resolve_repo", return_value=MOCK_REPO_DATA):
            result = runner.invoke(app, ["pr", "--base", "main", "--path", str(repo)])
            assert result.exit_code != 0
            assert "does not exist on remote 'origin'" in result.output
            assert "Push your branch first using 'nex git push" in result.output


def test_pr_unpushed_commits_rejected(git_repo_with_remote: Path) -> None:
    """Test nex pr rejects when local commits are ahead of remote tracking ref."""
    # Commit a new change locally without updating remote ref
    (git_repo_with_remote / "extra.py").write_text("print('extra')")
    subprocess.run(["git", "add", "extra.py"], cwd=git_repo_with_remote, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Unpushed commit"], cwd=git_repo_with_remote, check=True, capture_output=True)

    with patch("nex.commands.pr.get_stored_token", return_value="fake-token"):
        with patch("nex.commands.pr._resolve_repo", return_value=MOCK_REPO_DATA):
            result = runner.invoke(app, ["pr", "--base", "main", "--path", str(git_repo_with_remote)])
            assert result.exit_code != 0
            assert "unpushed commit(s) on local" in result.output
            assert "nex git push" in result.output


def test_pr_dry_run_success(git_repo_with_remote: Path) -> None:
    """Test nex pr --dry-run prints comparison preview without publishing to GitHub."""
    mock_client = MagicMock()
    mock_client.request.return_value = MOCK_PREVIEW_DATA

    with patch("nex.commands.pr.get_stored_token", return_value="fake-token"):
        with patch("nex.commands.pr._resolve_repo", return_value=MOCK_REPO_DATA):
            with patch("nex.core.context.CLIContext.client", mock_client):
                result = runner.invoke(
                    app,
                    ["pr", "--dry-run", "--path", str(git_repo_with_remote)],
                )
                assert result.exit_code == 0
                assert "PULL REQUEST PREVIEW" in result.output
                assert "[DRY-RUN]" in result.output
                assert "No PR was published to GitHub" in result.output
                # Verify preview was requested but create was NOT called
                mock_client.request.assert_called_once_with(
                    "POST",
                    "/repositories/11111111-2222-3333-4444-555555555555/pulls/preview/",
                    json={"head": "feature/my-feat", "base": "main"},
                )


def test_pr_create_approved_flow(git_repo_with_remote: Path) -> None:
    """Test nex pr creates PR with explicit human approval."""
    mock_client = MagicMock()
    # First call: preview, second call: create
    mock_client.request.side_effect = [MOCK_PREVIEW_DATA, MOCK_CREATED_PR]

    with patch("nex.commands.pr.get_stored_token", return_value="fake-token"):
        with patch("nex.commands.pr._resolve_repo", return_value=MOCK_REPO_DATA):
            with patch("nex.commands.pr.ApprovalPolicy.request_approval", return_value=True):
                with patch("nex.core.context.CLIContext.client", mock_client):
                    result = runner.invoke(
                        app,
                        [
                            "pr",
                            "--title",
                            "Add feature logic",
                            "--body",
                            "Feature details",
                            "--path",
                            str(git_repo_with_remote),
                        ],
                    )
                    assert result.exit_code == 0
                    assert "Pull Request #42 Published Successfully" in result.output
                    assert "https://github.com/test-org/test-repo/pull/42" in result.output


def test_pr_dry_run_json_mode(git_repo_with_remote: Path) -> None:
    """Test nex pr --dry-run --json outputs structured machine-readable payload."""
    mock_client = MagicMock()
    mock_client.request.return_value = MOCK_PREVIEW_DATA

    with patch("nex.commands.pr.get_stored_token", return_value="fake-token"):
        with patch("nex.commands.pr._resolve_repo", return_value=MOCK_REPO_DATA):
            with patch("nex.core.context.CLIContext.client", mock_client):
                result = runner.invoke(
                    app,
                    ["pr", "--dry-run", "--json", "--path", str(git_repo_with_remote)],
                )
                assert result.exit_code == 0
                data = json.loads(result.output)
                assert data["status"] == "ok"
                assert data["command"] == "pr.create"
                assert data["data"]["dry_run"] is True
                assert data["data"]["head"] == "feature/my-feat"


def test_pr_list_command() -> None:
    """Test nex pr list renders table of pull requests."""
    mock_client = MagicMock()
    mock_client.request.return_value = {
        "results": [
            MOCK_CREATED_PR,
            {
                "id": "22222222-3333-4444-5555-666666666666",
                "number": 43,
                "title": "Draft work in progress",
                "state": "open",
                "draft": True,
                "head_branch": "feature/draft",
                "base_branch": "main",
                "author_username": "other-user",
                "updated_at": "2026-11-03T18:30:00Z",
            },
        ]
    }

    with patch("nex.commands.pr.get_stored_token", return_value="fake-token"):
        with patch("nex.commands.pr._resolve_repo", return_value=MOCK_REPO_DATA):
            with patch("nex.core.context.CLIContext.client", mock_client):
                result = runner.invoke(app, ["pr", "list", "--repo", "11111111-2222-3333-4444-555555555555"])
                assert result.exit_code == 0
                assert "PULL REQUESTS — test-org/test-repo" in result.output
                assert "#42" in result.output
                assert "#43" in result.output
                assert "DRAFT" in result.output


def test_pr_view_command() -> None:
    """Test nex pr view renders single pull request details."""
    mock_client = MagicMock()
    mock_client.request.return_value = {
        **MOCK_CREATED_PR,
        "commits_count": 3,
        "additions": 45,
        "deletions": 12,
        "changed_files_count": 4,
    }

    with patch("nex.commands.pr.get_stored_token", return_value="fake-token"):
        with patch("nex.commands.pr._resolve_repo", return_value=MOCK_REPO_DATA):
            with patch("nex.core.context.CLIContext.client", mock_client):
                result = runner.invoke(app, ["pr", "view", "42", "--repo", "11111111-2222-3333-4444-555555555555"])
                assert result.exit_code == 0
                assert "#42: Add feature logic" in result.output
                assert "feature/my-feat → main" in result.output
                assert "https://github.com/test-org/test-repo/pull/42" in result.output


def test_pr_view_sync_flag() -> None:
    """Test nex pr view with --sync triggers backend GitHub sync."""
    mock_client = MagicMock()
    mock_client.request.return_value = MOCK_CREATED_PR

    with patch("nex.commands.pr.get_stored_token", return_value="fake-token"):
        with patch("nex.commands.pr._resolve_repo", return_value=MOCK_REPO_DATA):
            with patch("nex.core.context.CLIContext.client", mock_client):
                result = runner.invoke(app, ["pr", "view", "42", "--sync", "--repo", "11111111-2222-3333-4444-555555555555"])
                assert result.exit_code == 0
                mock_client.request.assert_called_once_with(
                    "POST",
                    "/repositories/11111111-2222-3333-4444-555555555555/pulls/42/sync/",
                )
