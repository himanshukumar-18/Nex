"""NEX Local Git Service & Repository Inspection.

Provides safe, typed subprocess execution for local Git operations.
Guarantees argument array execution (preventing shell injection), sensitive file
redaction in diff outputs, detached HEAD / shallow clone / merge state detection,
and robust error reporting.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nex.core.approvals import RiskLevel
from nex.core.exceptions import NexPolicyViolationError, NexRepositoryError
from nex.core.repository import (
    is_git_installed,
    is_sensitive_path,
    resolve_within_repository,
)

# Regex patterns for credential redacting within diff lines
SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----"),
    re.compile(r"AIzaSy[A-Za-z0-9_-]{33}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,255}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,72}"),
    re.compile(r"(?:api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^\s'\"]{8,}['\"]", re.IGNORECASE),
)


@dataclass(frozen=True)
class GitRemote:
    """Represents a configured Git remote repository."""

    name: str
    fetch_url: str
    push_url: str


@dataclass(frozen=True)
class GitBranch:
    """Represents a local or remote Git branch."""

    name: str
    is_current: bool
    commit_sha: str
    upstream: str | None = None
    is_remote: bool = False


@dataclass(frozen=True)
class GitCommit:
    """Represents a Git commit record."""

    sha: str
    short_sha: str
    author_name: str
    author_email: str
    date: str
    subject: str


@dataclass(frozen=True)
class GitDiffEntry:
    """Diff changes for a single modified or staged file."""

    file_path: str
    is_staged: bool
    is_binary: bool
    is_sensitive: bool
    additions: int
    deletions: int
    diff_content: str


@dataclass(frozen=True)
class GitState:
    """Comprehensive snapshot of a local repository's status and health."""

    is_git: bool
    root: Path | None = None
    git_dir: Path | None = None
    current_branch: str | None = None
    head_commit_sha: str | None = None
    head_commit_message: str | None = None
    is_detached_head: bool = False
    is_shallow: bool = False
    is_dirty: bool = False
    in_merge: bool = False
    in_rebase: bool = False
    in_cherry_pick: bool = False
    in_revert: bool = False
    staged_count: int = 0
    unstaged_count: int = 0
    untracked_count: int = 0
    remotes: list[GitRemote] = field(default_factory=list)
    git_version: str | None = None
    raw_status_lines: list[str] = field(default_factory=list)
    error_message: str | None = None


def run_git(
    args: list[str],
    repo_root: Path,
    timeout: float = 10.0,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Execute a git command safely via argument array (never shell string).

    Args:
        args: Command line parameters, e.g. ["status", "--porcelain"]
        repo_root: Working directory for execution
        timeout: Maximum duration before raising TimeoutExpired
        check: Whether to raise CalledProcessError if returncode != 0

    Raises:
        NexRepositoryError: If git binary is missing, path is invalid, or command times out.
    """
    if not is_git_installed():
        raise NexRepositoryError(
            "Git is not installed or not available on the system PATH.",
            suggestion="Install Git or ensure the git binary is in your PATH environment.",
        )

    if not repo_root.exists() or not repo_root.is_dir():
        raise NexRepositoryError(
            f"Repository directory does not exist or is not a directory: {repo_root}",
            suggestion="Check the provided repository path.",
        )

    cmd = ["git", *args]
    try:
        result = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=check,
            timeout=timeout,
        )
        return result
    except subprocess.TimeoutExpired as exc:
        raise NexRepositoryError(
            f"Git command timed out after {timeout} seconds: git {' '.join(args)}",
            suggestion="Verify repository integrity and check for lock files or background processes.",
        ) from exc
    except OSError as exc:
        raise NexRepositoryError(
            f"Failed to execute git command: {exc}",
            suggestion="Verify filesystem permissions and git binary integrity.",
        ) from exc


def get_git_version() -> str | None:
    """Retrieve installed git version string."""
    if not is_git_installed():
        return None
    try:
        res = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=3.0,
        )
        if res.returncode == 0:
            return res.stdout.strip().replace("git version ", "")
    except (subprocess.SubprocessError, OSError):
        pass
    return None


def get_git_root(start_path: Path | None = None) -> Path | None:
    """Locate the top-level root directory of a git repository."""
    current = (start_path or Path.cwd()).resolve()
    if not current.exists() or not current.is_dir():
        return None

    if is_git_installed():
        try:
            res = run_git(["rev-parse", "--show-toplevel"], current, timeout=3.0)
            if res.returncode == 0 and res.stdout.strip():
                top_level = Path(res.stdout.strip()).resolve()
                if top_level.is_dir():
                    return top_level
        except NexRepositoryError:
            pass

    # Filesystem traversal fallback
    for p in [current, *current.parents]:
        if (p / ".git").exists():
            return p
    return None


def detect_git_state(repo_root: Path) -> GitState:
    """Perform comprehensive inspection of git repository state and health."""
    if not is_git_installed():
        return GitState(
            is_git=False,
            error_message="Git binary is not installed on system PATH.",
        )

    if not repo_root.exists() or not repo_root.is_dir():
        return GitState(
            is_git=False,
            error_message=f"Path '{repo_root}' does not exist or is not a directory.",
        )

    # Verify if inside a git work tree
    res = run_git(["rev-parse", "--is-inside-work-tree"], repo_root)
    if res.returncode != 0 or res.stdout.strip() != "true":
        # Check if corrupted or simply not a git repo
        err = res.stderr.strip() or "Not a git repository"
        return GitState(
            is_git=False,
            root=repo_root,
            error_message=err,
        )

    # Resolve git directory (handles worktrees, submodules, and standard .git)
    git_dir_res = run_git(["rev-parse", "--git-dir"], repo_root)
    git_dir = (
        (repo_root / git_dir_res.stdout.strip()).resolve()
        if git_dir_res.returncode == 0
        else repo_root / ".git"
    )

    # 1. Branch and Detached HEAD detection
    branch_res = run_git(["symbolic-ref", "--short", "-q", "HEAD"], repo_root)
    is_detached = False
    current_branch: str | None = None

    if branch_res.returncode == 0 and branch_res.stdout.strip():
        current_branch = branch_res.stdout.strip()
    else:
        # HEAD is detached
        is_detached = True
        commit_res = run_git(["rev-parse", "--short", "HEAD"], repo_root)
        short_sha = commit_res.stdout.strip() if commit_res.returncode == 0 else "unknown"
        current_branch = f"HEAD (detached at {short_sha})"

    # 2. Shallow repository detection
    shallow_res = run_git(["rev-parse", "--is-shallow-repository"], repo_root)
    is_shallow = shallow_res.returncode == 0 and shallow_res.stdout.strip() == "true"
    if not is_shallow and (git_dir / "shallow").exists():
        is_shallow = True

    # 3. Head commit details
    head_sha: str | None = None
    head_msg: str | None = None
    log_res = run_git(["log", "-1", "--format=%h%x00%s"], repo_root)
    if log_res.returncode == 0 and log_res.stdout.strip():
        parts = log_res.stdout.strip().split("\x00", 1)
        head_sha = parts[0]
        head_msg = parts[1] if len(parts) > 1 else ""

    # 4. In-progress operation state (merge, rebase, cherry-pick, revert)
    in_merge = (git_dir / "MERGE_HEAD").exists()
    in_rebase = (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists()
    in_cherry_pick = (git_dir / "CHERRY_PICK_HEAD").exists()
    in_revert = (git_dir / "REVERT_HEAD").exists()

    # 5. Working tree status (porcelain v1)
    status_res = run_git(["status", "--porcelain=v1", "-uall"], repo_root)
    staged_count = 0
    unstaged_count = 0
    untracked_count = 0
    raw_lines: list[str] = []

    if status_res.returncode == 0:
        for line in status_res.stdout.splitlines():
            if not line or len(line) < 3:
                continue
            raw_lines.append(line)
            idx_st = line[0]
            wt_st = line[1]

            if idx_st not in {" ", "?"}:
                staged_count += 1
            if wt_st not in {" ", "?"}:
                unstaged_count += 1
            if idx_st == "?" and wt_st == "?":
                untracked_count += 1

    is_dirty = (staged_count + unstaged_count + untracked_count) > 0

    # 6. Remotes
    remotes = get_remotes(repo_root)

    # 7. Git version
    version = get_git_version()

    return GitState(
        is_git=True,
        root=repo_root,
        git_dir=git_dir,
        current_branch=current_branch,
        head_commit_sha=head_sha,
        head_commit_message=head_msg,
        is_detached_head=is_detached,
        is_shallow=is_shallow,
        is_dirty=is_dirty,
        in_merge=in_merge,
        in_rebase=in_rebase,
        in_cherry_pick=in_cherry_pick,
        in_revert=in_revert,
        staged_count=staged_count,
        unstaged_count=unstaged_count,
        untracked_count=untracked_count,
        remotes=remotes,
        git_version=version,
        raw_status_lines=raw_lines,
    )


def get_remotes(repo_root: Path) -> list[GitRemote]:
    """Retrieve all configured remotes with their fetch and push URLs."""
    res = run_git(["remote", "-v"], repo_root)
    if res.returncode != 0:
        return []

    remote_dict: dict[str, dict[str, str]] = {}
    for line in res.stdout.splitlines():
        parts = line.strip().split()
        if len(parts) >= 3:
            name, url, direction = parts[0], parts[1], parts[2]
            if name not in remote_dict:
                remote_dict[name] = {"fetch": "", "push": ""}
            if "(fetch)" in direction:
                remote_dict[name]["fetch"] = url
            elif "(push)" in direction:
                remote_dict[name]["push"] = url

    return [
        GitRemote(name=name, fetch_url=data["fetch"] or data["push"], push_url=data["push"] or data["fetch"])
        for name, data in remote_dict.items()
    ]


def list_branches(repo_root: Path, include_remotes: bool = False) -> list[GitBranch]:
    """List local and optionally remote branches with tracking upstream."""
    cmd = ["branch", "--list", "-vv"]
    if include_remotes:
        cmd.append("-a")

    res = run_git(cmd, repo_root)
    if res.returncode != 0:
        return []

    branches: list[GitBranch] = []
    # Pattern: [*(current)] [branch_name] [sha] [[upstream]] [subject]
    pattern = re.compile(
        r"^(\*|\s)\s+([^\s]+)\s+([0-9a-fA-F]+|\(no branch\))\s*(?:\[([^\]]+)\])?\s*(.*)$"
    )

    for line in res.stdout.splitlines():
        match = pattern.match(line)
        if not match:
            continue
        is_curr_mark, name, sha, upstream_info, _ = match.groups()
        if name.startswith("remotes/origin/HEAD"):
            continue

        is_current = is_curr_mark == "*"
        is_remote = name.startswith("remotes/")
        cleaned_name = name.removeprefix("remotes/")

        upstream = None
        if upstream_info:
            upstream = upstream_info.split(":")[0].strip()

        branches.append(
            GitBranch(
                name=cleaned_name,
                is_current=is_current,
                commit_sha=sha,
                upstream=upstream,
                is_remote=is_remote,
            )
        )

    return branches


def get_commit_history(repo_root: Path, limit: int = 10) -> list[GitCommit]:
    """Retrieve recent commit history formatted cleanly."""
    if limit <= 0:
        return []

    # Delimiter: NULL byte separation
    fmt = "%H%x00%h%x00%an%x00%ae%x00%ai%x00%s"
    res = run_git(["log", f"-n{limit}", f"--format={fmt}"], repo_root)
    if res.returncode != 0:
        return []

    commits: list[GitCommit] = []
    for line in res.stdout.splitlines():
        if not line:
            continue
        parts = line.split("\x00")
        if len(parts) >= 6:
            commits.append(
                GitCommit(
                    sha=parts[0],
                    short_sha=parts[1],
                    author_name=parts[2],
                    author_email=parts[3],
                    date=parts[4],
                    subject=parts[5],
                )
            )

    return commits


def _redact_diff_content(content: str) -> str:
    """Mask known credentials, API keys, and private keys in diff text."""
    redacted = content
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED SECRET]", redacted)
    return redacted


def get_diff(
    repo_root: Path,
    staged: bool = False,
    max_lines_per_file: int = 300,
) -> list[GitDiffEntry]:
    """Generate color-neutral unified diff entries with sensitive file redaction.

    Args:
        repo_root: Root of repository
        staged: If True, inspects staged changes (--staged); otherwise working tree changes
        max_lines_per_file: Line truncation cap to prevent memory exhaustion

    Returns:
        List of GitDiffEntry objects with additions, deletions, and redacted content.
    """
    args = ["diff", "--no-color", "--no-ext-diff"]
    if staged:
        args.append("--staged")

    res = run_git(args, repo_root)
    if res.returncode != 0:
        return []

    raw_diff = res.stdout
    if not raw_diff.strip():
        return []

    # Split by "diff --git " header
    file_chunks = raw_diff.split("diff --git ")
    diff_entries: list[GitDiffEntry] = []

    for chunk in file_chunks:
        if not chunk.strip():
            continue

        lines = chunk.splitlines()
        header_line = lines[0]  # e.g., "a/path/to/file b/path/to/file"
        parts = header_line.split(" ")
        file_path = parts[1][2:] if len(parts) >= 2 and parts[1].startswith("b/") else parts[0][2:]

        # Check for binary file
        is_binary = any("Binary files" in item for item in lines[:10])

        # Sensitive path check
        is_sensitive = is_sensitive_path(Path(file_path))

        additions = sum(1 for item in lines if item.startswith("+") and not item.startswith("+++"))
        deletions = sum(1 for item in lines if item.startswith("-") and not item.startswith("---"))

        if is_sensitive:
            diff_text = (
                f"diff --git {header_line}\n"
                f"[REDACTED SENSITIVE FILE — '{file_path}' matches sensitive credential/key pattern]\n"
            )
        elif is_binary:
            diff_text = f"diff --git {header_line}\n[Binary file differs]\n"
        else:
            # Mask secret patterns
            full_diff = f"diff --git {chunk}"
            # Truncate if exceedingly long
            chunk_lines = full_diff.splitlines()
            if len(chunk_lines) > max_lines_per_file:
                truncated_lines = chunk_lines[:max_lines_per_file]
                truncated_lines.append(
                    f"\n[... truncated {len(chunk_lines) - max_lines_per_file} lines for terminal safety ...]"
                )
                full_diff = "\n".join(truncated_lines)
            diff_text = _redact_diff_content(full_diff)

        diff_entries.append(
            GitDiffEntry(
                file_path=file_path,
                is_staged=staged,
                is_binary=is_binary,
                is_sensitive=is_sensitive,
                additions=additions,
                deletions=deletions,
                diff_content=diff_text,
            )
        )

    return diff_entries


def get_git_config(repo_root: Path) -> dict[str, str]:
    """Read local and global Git configuration key-value pairs."""
    res = run_git(["config", "--list"], repo_root)
    if res.returncode != 0:
        return {}

    configs: dict[str, str] = {}
    for line in res.stdout.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            configs[k.strip()] = v.strip()
    return configs


# ==============================================================================
# Phase 4 — Safe Git Operations (Branch, Stage, Commit, Push, Plan Verification)
# ==============================================================================


@dataclass(frozen=True)
class GitPlan:
    """Pre-execution blueprint capturing repository state for stale-plan detection."""

    operation: str
    repo_root: Path
    current_branch: str | None
    head_sha: str | None
    staged_count: int
    is_dirty: bool
    target_branch: str | None = None
    target_remote: str | None = None
    commit_message: str | None = None
    files: list[str] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.MEDIUM


def create_git_plan(
    operation: str,
    repo_root: Path,
    risk_level: RiskLevel = RiskLevel.MEDIUM,
    target_branch: str | None = None,
    target_remote: str | None = None,
    commit_message: str | None = None,
    files: list[str] | None = None,
) -> GitPlan:
    """Construct an operation plan capturing current working tree fingerprint."""
    state = detect_git_state(repo_root)
    return GitPlan(
        operation=operation,
        repo_root=repo_root,
        current_branch=state.current_branch,
        head_sha=state.head_commit_sha,
        staged_count=state.staged_count,
        is_dirty=state.is_dirty,
        target_branch=target_branch,
        target_remote=target_remote,
        commit_message=commit_message,
        files=list(files or []),
        risk_level=risk_level,
    )


def validate_plan_freshness(plan: GitPlan) -> None:
    """Verify repository state has not drifted between planning and execution."""
    current = detect_git_state(plan.repo_root)
    if current.current_branch != plan.current_branch:
        raise NexRepositoryError(
            f"Operation plan is stale: active branch changed from '{plan.current_branch}' to '{current.current_branch}'.",
            suggestion="Repository state drifted after approval. Please re-run the command.",
        )
    if current.head_commit_sha != plan.head_sha:
        raise NexRepositoryError(
            f"Operation plan is stale: HEAD commit changed from '{plan.head_sha}' to '{current.head_commit_sha}'.",
            suggestion="New commits were detected after approval. Please re-run the command.",
        )
    if current.staged_count != plan.staged_count:
        raise NexRepositoryError(
            f"Operation plan is stale: staged files count changed from {plan.staged_count} to {current.staged_count}.",
            suggestion="Index was modified after approval. Please re-run the command.",
        )


def validate_branch_name(branch_name: str, repo_root: Path) -> None:
    """Validate branch name against Git ref format rules and security constraints."""
    cleaned = branch_name.strip()
    if not cleaned:
        raise NexRepositoryError("Branch name cannot be empty.")

    if cleaned.startswith("-"):
        raise NexRepositoryError(
            f"Branch name cannot start with a hyphen: '{cleaned}'",
            suggestion="Avoid leading hyphens to prevent command option injection.",
        )

    if cleaned in {"HEAD", "@"}:
        raise NexRepositoryError(
            f"'{cleaned}' is a reserved Git ref name and cannot be used as a branch name."
        )

    # Git's authoritative ref format verification
    res = run_git(["check-ref-format", "--branch", cleaned], repo_root)
    if res.returncode != 0:
        raise NexRepositoryError(
            f"Invalid branch name '{cleaned}'.",
            suggestion=(
                "Git branch names cannot contain spaces, control characters, '..', "
                "'@{', ':', '?', '*', '[', '\\', or end with a slash."
            ),
        )


def create_branch(
    repo_root: Path,
    branch_name: str,
    start_point: str | None = None,
    dry_run: bool = False,
) -> None:
    """Create a new local branch with duplicate detection."""
    validate_branch_name(branch_name, repo_root)

    exists_res = run_git(["show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"], repo_root)
    if exists_res.returncode == 0:
        raise NexRepositoryError(
            f"Branch '{branch_name}' already exists locally in this repository.",
            suggestion="Choose a different branch name or switch to the existing branch.",
        )

    if dry_run:
        return

    cmd = ["branch", branch_name]
    if start_point:
        cmd.append(start_point)

    res = run_git(cmd, repo_root)
    if res.returncode != 0:
        raise NexRepositoryError(
            f"Failed to create branch '{branch_name}': {res.stderr.strip() or res.stdout.strip()}"
        )


def switch_branch(
    repo_root: Path,
    branch_name: str,
    dry_run: bool = False,
) -> None:
    """Switch the working tree to an existing local branch safely."""
    validate_branch_name(branch_name, repo_root)

    exists_res = run_git(["show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"], repo_root)
    if exists_res.returncode != 0:
        raise NexRepositoryError(
            f"Branch '{branch_name}' does not exist locally.",
            suggestion=f"Run 'nex git branch create {branch_name}' first to create it.",
        )

    state = detect_git_state(repo_root)
    if state.current_branch == branch_name:
        return  # Already on target branch

    if state.is_dirty:
        raise NexRepositoryError(
            f"Cannot switch to '{branch_name}' with uncommitted changes in working tree.",
            suggestion=(
                "Commit or stash your changes before switching branches. "
                "Run 'nex git status' to inspect modified files."
            ),
        )

    if state.in_merge or state.in_rebase or state.in_cherry_pick or state.in_revert:
        raise NexRepositoryError(
            "Cannot switch branches while an operation (merge, rebase, cherry-pick, revert) is in progress."
        )

    if dry_run:
        return

    res = run_git(["switch", branch_name], repo_root)
    if res.returncode != 0:
        # Fallback to checkout for older git versions
        checkout_res = run_git(["checkout", branch_name], repo_root)
        if checkout_res.returncode != 0:
            raise NexRepositoryError(
                f"Failed to switch to branch '{branch_name}': {checkout_res.stderr.strip()}"
            )


def stage_files(
    repo_root: Path,
    file_paths: list[str],
    dry_run: bool = False,
) -> list[str]:
    """Stage explicitly selected files into Git index with sensitive file blocking."""
    if not file_paths:
        raise NexRepositoryError("No files specified for staging.")

    validated_paths: list[str] = []
    for f in file_paths:
        clean_f = f.strip()
        if clean_f in {".", "*", "-A", "--all"} or clean_f.startswith("-"):
            raise NexPolicyViolationError(
                f"Wildcard or flag staging ('{clean_f}') is forbidden. Explicitly specify relative file paths."
            )

        resolved = resolve_within_repository(clean_f, repo_root)
        if is_sensitive_path(resolved):
            raise NexPolicyViolationError(
                f"Staging blocked: '{clean_f}' matches sensitive credential/secret patterns.",
                suggestion="NEX strictly prevents adding secrets (.env, *.key, *.pem) to the Git index.",
            )

        rel = str(resolved.relative_to(repo_root.resolve()))
        validated_paths.append(rel)

    if dry_run:
        return validated_paths

    res = run_git(["add", "--", *validated_paths], repo_root)
    if res.returncode != 0:
        raise NexRepositoryError(
            f"Failed to stage files: {res.stderr.strip() or res.stdout.strip()}"
        )

    return validated_paths


def unstage_files(
    repo_root: Path,
    file_paths: list[str],
    dry_run: bool = False,
) -> list[str]:
    """Remove explicitly selected files from the Git index without altering working tree."""
    if not file_paths:
        raise NexRepositoryError("No files specified for unstaging.")

    validated_paths: list[str] = []
    for f in file_paths:
        clean_f = f.strip()
        if clean_f.startswith("-"):
            raise NexPolicyViolationError(f"Invalid file argument '{clean_f}'.")

        resolved = resolve_within_repository(clean_f, repo_root)
        rel = str(resolved.relative_to(repo_root.resolve()))
        validated_paths.append(rel)

    if dry_run:
        return validated_paths

    res = run_git(["restore", "--staged", "--", *validated_paths], repo_root)
    if res.returncode != 0:
        # Fallback to git reset HEAD for older git
        reset_res = run_git(["reset", "HEAD", "--", *validated_paths], repo_root)
        if reset_res.returncode != 0:
            raise NexRepositoryError(
                f"Failed to unstage files: {reset_res.stderr.strip() or reset_res.stdout.strip()}"
            )

    return validated_paths


def get_staged_summary(repo_root: Path) -> dict[str, Any]:
    """Retrieve summary metrics and diff entries for all currently staged changes."""
    diff_entries = get_diff(repo_root, staged=True)
    total_additions = sum(d.additions for d in diff_entries)
    total_deletions = sum(d.deletions for d in diff_entries)

    files_info = [
        {
            "path": d.file_path,
            "file": d.file_path,
            "additions": d.additions,
            "insertions": d.additions,
            "deletions": d.deletions,
            "status": "M",
            "is_sensitive": d.is_sensitive,
            "is_binary": d.is_binary,
        }
        for d in diff_entries
    ]
    unified_diff = "\n".join(d.diff_content for d in diff_entries if d.diff_content)

    return {
        "count": len(diff_entries),
        "total_files": len(diff_entries),
        "files": files_info,
        "staged_files": files_info,
        "total_insertions": total_additions,
        "total_additions": total_additions,
        "total_deletions": total_deletions,
        "diff": unified_diff,
    }


def create_commit(
    repo_root: Path,
    message: str,
    dry_run: bool = False,
) -> GitCommit:
    """Create a new Git commit from staged changes with non-empty message enforcement."""
    clean_msg = message.strip()
    if not clean_msg:
        raise NexRepositoryError("Commit message cannot be empty.")

    state = detect_git_state(repo_root)
    if state.staged_count == 0:
        raise NexRepositoryError(
            "No staged changes to commit.",
            suggestion="Stage files first using 'nex git stage <files...>' before committing.",
        )

    if dry_run:
        return GitCommit(
            sha="dry-run",
            short_sha="dry-run",
            author_name="Developer",
            author_email="developer@nex.dev",
            date="now",
            subject=clean_msg,
        )

    res = run_git(["commit", "-m", clean_msg], repo_root)
    if res.returncode != 0:
        raise NexRepositoryError(
            f"Git commit failed: {res.stderr.strip() or res.stdout.strip()}"
        )

    commits = get_commit_history(repo_root, limit=1)
    if not commits:
        raise NexRepositoryError("Failed to parse newly created commit record.")

    return commits[0]


def push_branch(
    repo_root: Path,
    remote_name: str = "origin",
    branch_name: str | None = None,
    token: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Push approved local branch to remote repository using secure GIT_ASKPASS token authentication."""
    state = detect_git_state(repo_root)
    if state.is_detached_head:
        raise NexRepositoryError(
            "Cannot push while HEAD is detached.",
            suggestion="Switch to an active named branch before pushing.",
        )

    target_branch = branch_name or state.current_branch
    if not target_branch:
        raise NexRepositoryError("Unable to resolve active branch to push.")

    remotes = get_remotes(repo_root)
    matched_remote = next((r for r in remotes if r.name == remote_name), None)
    if not matched_remote:
        raise NexRepositoryError(
            f"Remote '{remote_name}' is not configured in this repository.",
            suggestion="Run 'nex git remotes' to see available remote targets.",
        )

    # Check for divergence / non-fast-forward
    try:
        fetch_res = run_git(["fetch", remote_name, target_branch], repo_root, timeout=10.0)
        if fetch_res.returncode == 0:
            count_res = run_git(
                ["rev-list", "--left-right", "--count", f"{remote_name}/{target_branch}...HEAD"],
                repo_root,
                timeout=5.0,
            )
            if count_res.returncode == 0 and count_res.stdout.strip():
                parts = count_res.stdout.strip().split()
                if len(parts) >= 2:
                    behind = int(parts[0])
                    if behind > 0:
                        raise NexRepositoryError(
                            f"Remote branch '{remote_name}/{target_branch}' has {behind} commits not in your local branch (diverged).",
                            suggestion=(
                                "Pull or rebase before pushing. "
                                "NEX strictly prohibits force-pushing to prevent data loss."
                            ),
                        )
    except subprocess.TimeoutExpired:
        pass  # Remote probe timed out; proceed to push attempt

    if dry_run:
        return {
            "status": "dry_run",
            "remote": remote_name,
            "branch": target_branch,
            "message": "Dry run: push validation succeeded. No remote mutations performed.",
        }

    # Execute secure push via temporary 0700 askpass script
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as f:
        f.write('#!/bin/sh\necho "$NEX_PUSH_TOKEN"\n')
        askpass_script = f.name

    os.chmod(askpass_script, 0o700)
    try:
        env = os.environ.copy()
        env["GIT_ASKPASS"] = askpass_script
        env["NEX_PUSH_TOKEN"] = token or ""
        env["GIT_TERMINAL_PROMPT"] = "0"

        push_res = subprocess.run(
            [
                "git",
                "push",
                remote_name,
                f"refs/heads/{target_branch}:refs/heads/{target_branch}",
            ],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=30.0,
        )

        if push_res.returncode != 0:
            err_msg = push_res.stderr.strip() or push_res.stdout.strip()
            if token:
                err_msg = err_msg.replace(token, "[REDACTED_TOKEN]")
            raise NexRepositoryError(f"Git push failed: {err_msg}")

        return {
            "status": "pushed",
            "remote": remote_name,
            "branch": target_branch,
        }
    finally:
        try:
            os.unlink(askpass_script)
        except OSError:
            pass

