"""Automated unit and integration test suite for Safe Git Operations (Phase 4).

Tests branch creation and switching, selective staging and unstaging,
sensitive file and wildcard guards, staged inspection with diff preview,
controlled commit creation, push operation validation with GIT_ASKPASS token handling,
risk classification policy enforcement (--yes restrictions), and stale plan detection.
"""

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from nex.core.approvals import RiskLevel
from nex.core.exceptions import (
    NexError,
    NexPolicyViolationError,
    NexRepositoryError,
)
from nex.core.git import (
    create_branch,
    create_commit,
    create_git_plan,
    detect_git_state,
    get_staged_summary,
    push_branch,
    stage_files,
    switch_branch,
    unstage_files,
    validate_branch_name,
    validate_plan_freshness,
)
from nex.main import NexTyper, app
from typer.testing import Result


class NexCliRunner:
    """Helper runner emulating Typer argument hoisting and domain exception handling."""

    def invoke(self, cli_app: Any, args: list[str], input: str | None = None) -> Result:
        from typer.testing import CliRunner

        runner = CliRunner()
        normalized = NexTyper._normalize_args(list(args))
        try:
            return runner.invoke(cli_app, normalized, input=input, catch_exceptions=False)
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

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "NEX Engineer"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "engineer@nex.test"], cwd=repo, check=True, capture_output=True)

    readme = repo / "README.md"
    readme.write_text("# Test Repository\nInitial content\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo, check=True, capture_output=True)

    return repo


# ─────────────────────────────────────────────────────────────────────────────
# 1. Branch Management Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_validate_branch_name(temp_git_repo: Path) -> None:
    """Verify branch naming validation rules and injection guards."""
    # Valid names
    validate_branch_name("feature/user-auth", temp_git_repo)
    validate_branch_name("fix-123", temp_git_repo)
    validate_branch_name("release/v1.0.0", temp_git_repo)

    # Empty name
    with pytest.raises(NexRepositoryError, match="cannot be empty"):
        validate_branch_name("", temp_git_repo)

    # Leading hyphen (option injection prevention)
    with pytest.raises(NexRepositoryError, match="cannot start with a hyphen"):
        validate_branch_name("-invalid", temp_git_repo)

    # Reserved ref names
    with pytest.raises(NexRepositoryError, match="reserved Git ref name"):
        validate_branch_name("HEAD", temp_git_repo)

    # Invalid characters
    with pytest.raises(NexRepositoryError, match="Invalid branch name"):
        validate_branch_name("invalid branch with spaces", temp_git_repo)


def test_create_branch_and_duplicate_detection(temp_git_repo: Path) -> None:
    """Verify branch creation and duplicate rejection."""
    # Create new branch
    create_branch(temp_git_repo, "feature/billing")

    # Verify branch exists
    res = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", "refs/heads/feature/billing"],
        cwd=temp_git_repo,
    )
    assert res.returncode == 0

    # Duplicate branch creation must be rejected
    with pytest.raises(NexRepositoryError, match="already exists locally"):
        create_branch(temp_git_repo, "feature/billing")


def test_create_branch_dry_run(temp_git_repo: Path) -> None:
    """Verify dry-run does not modify repository."""
    create_branch(temp_git_repo, "feature/dry-run-test", dry_run=True)

    res = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", "refs/heads/feature/dry-run-test"],
        cwd=temp_git_repo,
    )
    assert res.returncode != 0


def test_switch_branch_clean_tree(temp_git_repo: Path) -> None:
    """Verify switching to an existing branch succeeds on clean working tree."""
    create_branch(temp_git_repo, "feature/checkout-test")
    switch_branch(temp_git_repo, "feature/checkout-test")

    state = detect_git_state(temp_git_repo)
    assert state.current_branch == "feature/checkout-test"


def test_switch_branch_dirty_tree_rejected(temp_git_repo: Path) -> None:
    """Verify branch switch is blocked when uncommitted changes exist."""
    create_branch(temp_git_repo, "feature/target-branch")

    # Create uncommitted dirty file
    dirty_file = temp_git_repo / "dirty.txt"
    dirty_file.write_text("uncommitted changes")

    with pytest.raises(NexRepositoryError, match="uncommitted changes in working tree"):
        switch_branch(temp_git_repo, "feature/target-branch")


def test_switch_branch_nonexistent_rejected(temp_git_repo: Path) -> None:
    """Verify switching to non-existent branch is rejected."""
    with pytest.raises(NexRepositoryError, match="does not exist locally"):
        switch_branch(temp_git_repo, "nonexistent-branch")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Selective Staging & Sensitive File Guards
# ─────────────────────────────────────────────────────────────────────────────


def test_stage_files_selective(temp_git_repo: Path) -> None:
    """Verify explicit file staging adds only targeted files to index."""
    file_a = temp_git_repo / "file_a.txt"
    file_b = temp_git_repo / "file_b.txt"
    file_a.write_text("Content A")
    file_b.write_text("Content B")

    # Stage only file_a
    staged = stage_files(temp_git_repo, ["file_a.txt"])
    assert len(staged) == 1
    assert "file_a.txt" in str(staged[0])

    state = detect_git_state(temp_git_repo)
    assert state.staged_count == 1
    assert state.untracked_count == 1  # file_b remains untracked


def test_stage_files_wildcard_rejected(temp_git_repo: Path) -> None:
    """Verify wildcard staging is strictly blocked."""
    with pytest.raises(NexPolicyViolationError, match=r"Wildcard.*staging"):
        stage_files(temp_git_repo, ["."])

    with pytest.raises(NexPolicyViolationError, match=r"Wildcard.*staging"):
        stage_files(temp_git_repo, ["*"])


def test_stage_files_sensitive_path_blocked(temp_git_repo: Path) -> None:
    """Verify sensitive files (.env, service account keys) are blocked from staging."""
    env_file = temp_git_repo / ".env"
    env_file.write_text("SECRET_KEY=supersecret123\n")

    with pytest.raises(NexPolicyViolationError, match=r"Staging blocked.*sensitive"):
        stage_files(temp_git_repo, [".env"])

    sa_file = temp_git_repo / "service-account.json"
    sa_file.write_text('{"type": "service_account"}')

    with pytest.raises(NexPolicyViolationError, match=r"Staging blocked.*sensitive"):
        stage_files(temp_git_repo, ["service-account.json"])


def test_stage_files_path_traversal_blocked(temp_git_repo: Path) -> None:
    """Verify path traversal outside repo root is strictly blocked."""
    with pytest.raises(NexPolicyViolationError, match=r"Path traversal detected"):
        stage_files(temp_git_repo, ["../../outside.txt"])


def test_unstage_files(temp_git_repo: Path) -> None:
    """Verify unstage removes files from index without modifying working tree."""
    file_a = temp_git_repo / "file_a.txt"
    file_a.write_text("Content A")
    stage_files(temp_git_repo, ["file_a.txt"])

    state_before = detect_git_state(temp_git_repo)
    assert state_before.staged_count == 1

    unstaged = unstage_files(temp_git_repo, ["file_a.txt"])
    assert len(unstaged) == 1

    state_after = detect_git_state(temp_git_repo)
    assert state_after.staged_count == 0
    assert file_a.exists()  # Working tree file preserved


def test_get_staged_summary(temp_git_repo: Path) -> None:
    """Verify staged summary returns count, file details, and secret-redacted diff."""
    file_a = temp_git_repo / "auth.py"
    file_a.write_text("TOKEN = 'AIzaSy123456789012345678901234567890123'\n")
    stage_files(temp_git_repo, ["auth.py"])

    summary = get_staged_summary(temp_git_repo)
    assert summary["count"] == 1
    assert summary["total_insertions"] > 0
    assert len(summary["files"]) == 1
    assert summary["files"][0]["path"] == "auth.py"
    # Verify secret is redacted in diff
    assert "AIzaSy123456789012345678901234567890123" not in summary["diff"]
    assert "[REDACTED SECRET]" in summary["diff"]


# ─────────────────────────────────────────────────────────────────────────────
# 3. Commit Creation Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_create_commit_success(temp_git_repo: Path) -> None:
    """Verify successful commit creation from staged changes."""
    work_file = temp_git_repo / "work.txt"
    work_file.write_text("Completed work\n")
    stage_files(temp_git_repo, ["work.txt"])

    commit = create_commit(temp_git_repo, "Implement core feature")
    assert commit.sha != "dry-run"
    assert commit.subject == "Implement core feature"
    assert commit.author_name == "NEX Engineer"

    state = detect_git_state(temp_git_repo)
    assert state.staged_count == 0
    assert state.head_commit_sha == commit.short_sha


def test_create_commit_empty_message_rejected(temp_git_repo: Path) -> None:
    """Verify commit with empty or whitespace message is rejected."""
    work_file = temp_git_repo / "work.txt"
    work_file.write_text("Completed work\n")
    stage_files(temp_git_repo, ["work.txt"])

    with pytest.raises(NexRepositoryError, match="cannot be empty"):
        create_commit(temp_git_repo, "   ")


def test_create_commit_nothing_staged_rejected(temp_git_repo: Path) -> None:
    """Verify commit fails if nothing is staged in the index."""
    with pytest.raises(NexRepositoryError, match="No staged changes"):
        create_commit(temp_git_repo, "Commit with empty index")


def test_create_commit_dry_run(temp_git_repo: Path) -> None:
    """Verify dry-run commit does not mutate repository."""
    work_file = temp_git_repo / "work.txt"
    work_file.write_text("Completed work\n")
    stage_files(temp_git_repo, ["work.txt"])

    state_before = detect_git_state(temp_git_repo)
    commit = create_commit(temp_git_repo, "Dry run commit", dry_run=True)
    assert commit.sha == "dry-run"

    state_after = detect_git_state(temp_git_repo)
    assert state_after.head_commit_sha == state_before.head_commit_sha
    assert state_after.staged_count == 1  # Still staged


# ─────────────────────────────────────────────────────────────────────────────
# 4. Push Operation Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_push_detached_head_rejected(temp_git_repo: Path) -> None:
    """Verify push is rejected when HEAD is detached."""
    state = detect_git_state(temp_git_repo)
    assert state.head_commit_sha is not None
    # Detach HEAD
    subprocess.run(["git", "checkout", state.head_commit_sha], cwd=temp_git_repo, check=True, capture_output=True)

    with pytest.raises(NexRepositoryError, match="HEAD is detached"):
        push_branch(temp_git_repo, "origin")


def test_push_unconfigured_remote_rejected(temp_git_repo: Path) -> None:
    """Verify push is rejected if remote is not configured."""
    with pytest.raises(NexRepositoryError, match="Remote 'nonexistent' is not configured"):
        push_branch(temp_git_repo, "nonexistent")


def test_push_dry_run_success(temp_git_repo: Path) -> None:
    """Verify push dry-run validates remote and returns simulated status."""
    # Add dummy remote
    subprocess.run(["git", "remote", "add", "origin", "https://github.com/nex-dev/demo.git"], cwd=temp_git_repo, check=True)

    res = push_branch(temp_git_repo, "origin", dry_run=True)
    assert res["status"] == "dry_run"
    assert res["remote"] == "origin"
    assert res["branch"] == "main"


# ─────────────────────────────────────────────────────────────────────────────
# 5. Stale-Plan Detection Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_stale_plan_detection(temp_git_repo: Path) -> None:
    """Verify repository drift after planning raises stale plan error."""
    plan = create_git_plan("commit", temp_git_repo, risk_level=RiskLevel.HIGH)

    # 1. Freshness check passes when untouched
    validate_plan_freshness(plan)

    # 2. Stage a file -> staged_count drifts
    dummy = temp_git_repo / "dummy.txt"
    dummy.write_text("drift")
    subprocess.run(["git", "add", "dummy.txt"], cwd=temp_git_repo, check=True)

    with pytest.raises(NexRepositoryError, match="Operation plan is stale.*staged files count changed"):
        validate_plan_freshness(plan)


# ─────────────────────────────────────────────────────────────────────────────
# 6. CLI Command Workflows & Approval Policy Verification
# ─────────────────────────────────────────────────────────────────────────────


def test_cli_branch_list(temp_git_repo: Path) -> None:
    """Verify 'nex git branch list' CLI output and JSON formatting."""
    res = runner.invoke(app, ["git", "branch", "list", "--path", str(temp_git_repo)])
    assert res.exit_code == 0
    assert "main" in res.stdout

    res_json = runner.invoke(app, ["--json", "git", "branch", "list", "--path", str(temp_git_repo)])
    assert res_json.exit_code == 0
    parsed = json.loads(res_json.stdout)
    assert parsed["status"] == "ok"
    assert "main" in [b["name"] for b in parsed["data"]["branches"]]


def test_cli_branch_create_and_switch(temp_git_repo: Path) -> None:
    """Verify 'nex git branch create' and 'nex git branch switch' with --yes."""
    # Create branch
    res_create = runner.invoke(
        app,
        ["git", "branch", "create", "feature/cli-test", "--yes", "--path", str(temp_git_repo)],
    )
    assert res_create.exit_code == 0
    assert "created successfully" in res_create.stdout

    # Switch branch
    res_switch = runner.invoke(
        app,
        ["git", "branch", "switch", "feature/cli-test", "--yes", "--path", str(temp_git_repo)],
    )
    assert res_switch.exit_code == 0
    assert "Switched to branch 'feature/cli-test'" in res_switch.stdout

    state = detect_git_state(temp_git_repo)
    assert state.current_branch == "feature/cli-test"


def test_cli_stage_yes_flag_prohibited(temp_git_repo: Path) -> None:
    """Verify that --yes flag is strictly prohibited for HIGH-risk stage operation."""
    work = temp_git_repo / "file.py"
    work.write_text("x = 1\n")

    res = runner.invoke(
        app,
        ["git", "stage", "file.py", "--yes", "--path", str(temp_git_repo)],
    )
    assert res.exit_code != 0
    assert "Flag '--yes' cannot bypass approval for HIGH-risk operation" in res.stdout


def test_cli_stage_and_staged_flow(temp_git_repo: Path) -> None:
    """Verify staging workflow and staged inspection."""
    work = temp_git_repo / "service.py"
    work.write_text("def run(): pass\n")

    with patch("nex.commands.git.ApprovalPolicy.request_approval", return_value=True):
        res = runner.invoke(
            app,
            ["git", "stage", "service.py", "--path", str(temp_git_repo)],
        )
    assert res.exit_code == 0
    assert "Staged 1 file(s)" in res.stdout

    # Inspect staged
    res_staged = runner.invoke(
        app,
        ["git", "staged", "--path", str(temp_git_repo)],
    )
    assert res_staged.exit_code == 0
    assert "service.py" in res_staged.stdout


def test_cli_unstage_flow(temp_git_repo: Path) -> None:
    """Verify unstaging files via CLI."""
    work = temp_git_repo / "service.py"
    work.write_text("def run(): pass\n")
    stage_files(temp_git_repo, ["service.py"])

    with patch("nex.commands.git.ApprovalPolicy.request_approval", return_value=True):
        res = runner.invoke(
            app,
            ["git", "unstage", "service.py", "--path", str(temp_git_repo)],
        )
    assert res.exit_code == 0
    assert "Unstaged 1 file(s)" in res.stdout

    state = detect_git_state(temp_git_repo)
    assert state.staged_count == 0


def test_cli_commit_yes_flag_prohibited(temp_git_repo: Path) -> None:
    """Verify that --yes flag is strictly prohibited for HIGH-risk commit operation."""
    work = temp_git_repo / "service.py"
    work.write_text("def run(): pass\n")
    stage_files(temp_git_repo, ["service.py"])

    res = runner.invoke(
        app,
        ["git", "commit", "-m", "Add service", "--yes", "--path", str(temp_git_repo)],
    )
    assert res.exit_code != 0
    assert "Flag '--yes' cannot bypass approval for HIGH-risk operation" in res.stdout


def test_cli_commit_flow(temp_git_repo: Path) -> None:
    """Verify commit creation with approval."""
    work = temp_git_repo / "service.py"
    work.write_text("def run(): pass\n")
    stage_files(temp_git_repo, ["service.py"])

    with patch("nex.commands.git.ApprovalPolicy.request_approval", return_value=True):
        res = runner.invoke(
            app,
            ["git", "commit", "-m", "Add service implementation", "--path", str(temp_git_repo)],
        )
    assert res.exit_code == 0
    assert "Commit created" in res.stdout
    assert "Add service implementation" in res.stdout


def test_cli_push_yes_flag_prohibited(temp_git_repo: Path) -> None:
    """Verify that --yes flag is strictly prohibited for CRITICAL-risk push operation."""
    subprocess.run(["git", "remote", "add", "origin", "https://github.com/nex-dev/demo.git"], cwd=temp_git_repo, check=True)

    res = runner.invoke(
        app,
        ["git", "push", "--yes", "--path", str(temp_git_repo)],
    )
    assert res.exit_code != 0
    assert "Flag '--yes' cannot bypass approval for CRITICAL-risk operation" in res.stdout


def test_cli_push_dry_run(temp_git_repo: Path) -> None:
    """Verify push --dry-run succeeds without modifying remote."""
    subprocess.run(["git", "remote", "add", "origin", "https://github.com/nex-dev/demo.git"], cwd=temp_git_repo, check=True)

    res = runner.invoke(
        app,
        ["git", "push", "--dry-run", "--path", str(temp_git_repo)],
    )
    assert res.exit_code == 0
    assert "Push validation succeeded" in res.stdout
