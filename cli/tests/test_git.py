"""Automated unit and integration test suite for local Git foundation (Phase 1).

Tests repository state detection, detached HEAD, shallow clones, in-progress operations
(merge, rebase, cherry-pick), sensitive file/token redaction in diffs, safe subprocess
argument handling, and CLI command workflows in both terminal and JSON modes.
"""

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from nex.core.exceptions import NexError, NexRepositoryError
from nex.core.git import (
    detect_git_state,
    get_commit_history,
    get_diff,
    get_git_config,
    get_remotes,
    list_branches,
    run_git,
)
from nex.main import NexTyper, app
from typer.testing import Result


class NexCliRunner:
    """Helper runner emulating Typer argument hoisting and domain exception handling."""

    def invoke(self, cli_app: Any, args: list[str]) -> Result:
        from typer.testing import CliRunner

        runner = CliRunner()
        normalized = NexTyper._normalize_args(list(args))
        try:
            return runner.invoke(cli_app, normalized, catch_exceptions=False)
        except NexError as err:
            msg = f"✕ ERROR: {err.message}\n"
            return Result(
                runner=runner,
                stdout_bytes=msg.encode(),
                stderr_bytes=b"",
                output_bytes=msg.encode(),
                return_value=None,
                exit_code=err.exit_code,
                exception=err,
            )


runner = NexCliRunner()


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    """Creates a fully initialized, clean Git repository in a temporary directory."""
    repo = tmp_path / "test_repo"
    repo.mkdir()

    # Configure user name/email locally
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test Engineer"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "engineer@nex.test"], cwd=repo, check=True, capture_output=True)

    # Initial commit
    readme = repo / "README.md"
    readme.write_text("# Test Repository\nInitial content\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo, check=True, capture_output=True)

    return repo


# ─────────────────────────────────────────────────────────────────────────────
# 1. State Detection & Integrity Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_detect_git_state_clean_repo(temp_git_repo: Path) -> None:
    """Verify state detection on a clean, standard git repository."""
    state = detect_git_state(temp_git_repo)

    assert state.is_git is True
    assert state.root == temp_git_repo
    assert state.current_branch == "main"
    assert state.head_commit_sha is not None
    assert state.head_commit_message == "Initial commit"
    assert state.is_detached_head is False
    assert state.is_shallow is False
    assert state.is_dirty is False
    assert state.in_merge is False
    assert state.in_rebase is False
    assert state.staged_count == 0
    assert state.unstaged_count == 0
    assert state.untracked_count == 0


def test_detect_git_state_dirty_repo(temp_git_repo: Path) -> None:
    """Verify dirty repository detection with staged, unstaged, and untracked files."""
    # Staged change
    file_staged = temp_git_repo / "staged.txt"
    file_staged.write_text("staged content")
    subprocess.run(["git", "add", "staged.txt"], cwd=temp_git_repo, check=True)

    # Unstaged modified change
    readme = temp_git_repo / "README.md"
    readme.write_text("# Test Repository\nModified content\n")

    # Untracked change
    untracked = temp_git_repo / "untracked.py"
    untracked.write_text("print('hello')")

    state = detect_git_state(temp_git_repo)
    assert state.is_dirty is True
    assert state.staged_count == 1
    assert state.unstaged_count == 1
    assert state.untracked_count == 1


def test_detect_git_state_detached_head(temp_git_repo: Path) -> None:
    """Verify detection of detached HEAD state."""
    # Make a second commit
    f2 = temp_git_repo / "file2.txt"
    f2.write_text("file2")
    subprocess.run(["git", "add", "file2.txt"], cwd=temp_git_repo, check=True)
    subprocess.run(["git", "commit", "-m", "Second commit"], cwd=temp_git_repo, check=True)

    # Detach HEAD by checking out HEAD~1 commit directly
    subprocess.run(["git", "checkout", "HEAD~1"], cwd=temp_git_repo, check=True, capture_output=True)

    state = detect_git_state(temp_git_repo)
    assert state.is_git is True
    assert state.is_detached_head is True
    assert state.current_branch is not None
    assert "HEAD (detached at" in state.current_branch


def test_detect_git_state_shallow_clone(temp_git_repo: Path) -> None:
    """Verify shallow clone detection flag."""
    # Simulate shallow clone marker
    shallow_file = temp_git_repo / ".git" / "shallow"
    shallow_file.write_text("0123456789abcdef\n")

    state = detect_git_state(temp_git_repo)
    assert state.is_shallow is True


def test_detect_git_state_in_progress_operations(temp_git_repo: Path) -> None:
    """Verify in-progress operation markers (merge, rebase, cherry-pick, revert)."""
    git_dir = temp_git_repo / ".git"

    # Merge marker
    merge_head = git_dir / "MERGE_HEAD"
    merge_head.write_text("0123456789abcdef\n")
    state = detect_git_state(temp_git_repo)
    assert state.in_merge is True
    merge_head.unlink()

    # Rebase marker
    rebase_dir = git_dir / "rebase-merge"
    rebase_dir.mkdir()
    state = detect_git_state(temp_git_repo)
    assert state.in_rebase is True
    rebase_dir.rmdir()

    # Cherry-pick marker
    cp_head = git_dir / "CHERRY_PICK_HEAD"
    cp_head.write_text("0123456789abcdef\n")
    state = detect_git_state(temp_git_repo)
    assert state.in_cherry_pick is True
    cp_head.unlink()

    # Revert marker
    rev_head = git_dir / "REVERT_HEAD"
    rev_head.write_text("0123456789abcdef\n")
    state = detect_git_state(temp_git_repo)
    assert state.in_revert is True
    rev_head.unlink()


def test_detect_git_state_non_git_directory(tmp_path: Path) -> None:
    """Verify clean reporting when directory is not a git repository."""
    non_git = tmp_path / "not_git"
    non_git.mkdir()

    state = detect_git_state(non_git)
    assert state.is_git is False
    assert state.error_message is not None


def test_detect_git_state_missing_git_binary(temp_git_repo: Path) -> None:
    """Verify handling when git binary is not found on PATH."""
    with patch("nex.core.git.is_git_installed", return_value=False):
        state = detect_git_state(temp_git_repo)
        assert state.is_git is False
        assert "Git binary is not installed" in (state.error_message or "")


def test_run_git_missing_binary_raises_nex_error(temp_git_repo: Path) -> None:
    """run_git must raise NexRepositoryError if git binary is absent."""
    with patch("nex.core.git.is_git_installed", return_value=False):
        with pytest.raises(NexRepositoryError, match="Git is not installed"):
            run_git(["status"], temp_git_repo)


def test_run_git_invalid_path_raises_nex_error(tmp_path: Path) -> None:
    """run_git must raise NexRepositoryError if path does not exist."""
    invalid_path = tmp_path / "does_not_exist"
    with pytest.raises(NexRepositoryError, match="does not exist"):
        run_git(["status"], invalid_path)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Branch, Commit, and Remote Inspection Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_list_branches(temp_git_repo: Path) -> None:
    """Verify listing branches and highlighting current branch."""
    # Create feature branch
    subprocess.run(["git", "branch", "feature/auth"], cwd=temp_git_repo, check=True)

    branches = list_branches(temp_git_repo, include_remotes=False)
    assert len(branches) == 2
    names = {b.name for b in branches}
    assert "main" in names
    assert "feature/auth" in names

    current_branches = [b for b in branches if b.is_current]
    assert len(current_branches) == 1
    assert current_branches[0].name == "main"


def test_get_commit_history(temp_git_repo: Path) -> None:
    """Verify retrieving commit history."""
    f = temp_git_repo / "changelog.txt"
    f.write_text("v1.0")
    subprocess.run(["git", "add", "changelog.txt"], cwd=temp_git_repo, check=True)
    subprocess.run(["git", "commit", "-m", "Add changelog"], cwd=temp_git_repo, check=True)

    commits = get_commit_history(temp_git_repo, limit=5)
    assert len(commits) == 2
    assert commits[0].subject == "Add changelog"
    assert commits[0].author_name == "Test Engineer"
    assert commits[1].subject == "Initial commit"


def test_get_remotes(temp_git_repo: Path) -> None:
    """Verify parsing configured git remotes."""
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/nex/nex-platform.git"],
        cwd=temp_git_repo,
        check=True,
    )
    remotes = get_remotes(temp_git_repo)
    assert len(remotes) == 1
    assert remotes[0].name == "origin"
    assert "https://github.com/nex/nex-platform.git" in remotes[0].fetch_url


def test_get_git_config(temp_git_repo: Path) -> None:
    """Verify reading repository configuration."""
    configs = get_git_config(temp_git_repo)
    assert configs.get("user.name") == "Test Engineer"
    assert configs.get("user.email") == "engineer@nex.test"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Diff and Secret Redaction Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_diff_sensitive_file_redaction(temp_git_repo: Path) -> None:
    """Verify that diffs for sensitive files (.env, keys) are strictly redacted."""
    # Create sensitive .env file
    env_file = temp_git_repo / ".env"
    env_file.write_text("SUPER_SECRET_KEY=secret_value_12345\n")
    subprocess.run(["git", "add", ".env"], cwd=temp_git_repo, check=True)

    diffs = get_diff(temp_git_repo, staged=True)
    assert len(diffs) == 1
    d = diffs[0]
    assert d.file_path == ".env"
    assert d.is_sensitive is True
    assert "secret_value_12345" not in d.diff_content
    assert "[REDACTED SENSITIVE FILE" in d.diff_content


def test_diff_secret_token_redaction(temp_git_repo: Path) -> None:
    """Verify that credentials within regular files are masked."""
    source_file = temp_git_repo / "app.py"
    source_file.write_text(
        '# Secret test\nAPI_KEY = "AIzaSyDummyGoogleApiKey1234567890"\n'
    )
    subprocess.run(["git", "add", "app.py"], cwd=temp_git_repo, check=True)
    diffs = get_diff(temp_git_repo, staged=True)
    assert len(diffs) == 1
    d = diffs[0]
    assert "AIzaSyDummyGoogleApiKey1234567890" not in d.diff_content
    assert "[REDACTED SECRET]" in d.diff_content


# ─────────────────────────────────────────────────────────────────────────────
# 4. CLI Subcommand End-to-End Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_cli_git_status_command(temp_git_repo: Path) -> None:
    """Test nex git status in terminal and JSON mode."""
    # Terminal
    res1 = runner.invoke(app, ["git", "status", "--path", str(temp_git_repo)])
    assert res1.exit_code == 0
    assert "GIT STATUS" in res1.output
    assert "main" in res1.output
    assert "CLEAN" in res1.output

    # JSON mode
    res2 = runner.invoke(app, ["git", "status", "--path", str(temp_git_repo), "--json"])
    assert res2.exit_code == 0
    data = json.loads(res2.output)
    assert data["status"] == "ok"
    assert data["command"] == "git.status"
    assert data["data"]["branch"] == "main"
    assert data["data"]["is_dirty"] is False


def test_cli_git_branches_command(temp_git_repo: Path) -> None:
    """Test nex git branches in terminal and JSON mode."""
    res1 = runner.invoke(app, ["git", "branches", "--path", str(temp_git_repo)])
    assert res1.exit_code == 0
    assert "GIT BRANCHES" in res1.output
    assert "main" in res1.output

    res2 = runner.invoke(app, ["git", "branches", "--path", str(temp_git_repo), "--json"])
    assert res2.exit_code == 0
    data = json.loads(res2.output)
    assert data["status"] == "ok"
    assert len(data["data"]["branches"]) >= 1


def test_cli_git_log_command(temp_git_repo: Path) -> None:
    """Test nex git log in terminal and JSON mode."""
    res1 = runner.invoke(app, ["git", "log", "--limit", "1", "--path", str(temp_git_repo)])
    assert res1.exit_code == 0
    assert "GIT COMMIT LOG" in res1.output
    assert "Initial commit" in res1.output

    res2 = runner.invoke(app, ["git", "log", "-n", "1", "--path", str(temp_git_repo), "--json"])
    assert res2.exit_code == 0
    data = json.loads(res2.output)
    assert len(data["data"]["commits"]) == 1
    assert data["data"]["commits"][0]["subject"] == "Initial commit"


def test_cli_git_diff_command(temp_git_repo: Path) -> None:
    """Test nex git diff and nex git diff --stat."""
    f = temp_git_repo / "README.md"
    f.write_text("# Test Repository\nAdded line\n")

    res1 = runner.invoke(app, ["git", "diff", "--path", str(temp_git_repo)])
    assert res1.exit_code == 0
    assert "GIT DIFF" in res1.output
    assert "README.md" in res1.output

    res2 = runner.invoke(app, ["git", "diff", "--stat", "--path", str(temp_git_repo)])
    assert res2.exit_code == 0
    assert "DIFF STATISTICS" in res2.output

    res3 = runner.invoke(app, ["git", "diff", "--json", "--path", str(temp_git_repo)])
    assert res3.exit_code == 0
    data = json.loads(res3.output)
    assert data["data"]["files_changed"] == 1


def test_cli_git_remotes_command(temp_git_repo: Path) -> None:
    """Test nex git remotes in terminal and JSON mode."""
    subprocess.run(["git", "remote", "add", "origin", "https://github.com/nex/demo.git"], cwd=temp_git_repo, check=True)

    res1 = runner.invoke(app, ["git", "remotes", "--path", str(temp_git_repo)])
    assert res1.exit_code == 0
    assert "GIT REMOTES" in res1.output
    assert "origin" in res1.output

    res2 = runner.invoke(app, ["git", "remotes", "--path", str(temp_git_repo), "--json"])
    assert res2.exit_code == 0
    data = json.loads(res2.output)
    assert len(data["data"]["remotes"]) == 1
    assert data["data"]["remotes"][0]["name"] == "origin"


def test_cli_git_inspect_command(temp_git_repo: Path) -> None:
    """Test nex git inspect in terminal and JSON mode."""
    res1 = runner.invoke(app, ["git", "inspect", "--path", str(temp_git_repo)])
    assert res1.exit_code == 0
    assert "GIT DIAGNOSTIC INSPECTION" in res1.output
    assert "main" in res1.output

    res2 = runner.invoke(app, ["git", "inspect", "--path", str(temp_git_repo), "--json"])
    assert res2.exit_code == 0
    data = json.loads(res2.output)
    assert data["data"]["branch"] == "main"
    assert data["data"]["is_detached_head"] is False


def test_cli_git_on_non_git_directory(tmp_path: Path) -> None:
    """Test nex git status raises NexRepositoryError when invoked outside git repository."""
    non_git = tmp_path / "empty_dir"
    non_git.mkdir()

    res = runner.invoke(app, ["git", "status", "--path", str(non_git)])
    assert res.exit_code != 0
    assert "ERROR" in res.output or "not a Git repository" in res.output
