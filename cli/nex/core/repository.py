"""NEX Local Repository Discovery & Safety Utilities.

Provides secure inspection of local git repositories, root resolution,
safe path resolution, symlink boundary checks, and sensitive file exclusion.
"""

import fnmatch
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nex.core.exceptions import NexPolicyViolationError, NexRepositoryError

# Patterns strictly excluded from repository file inventories and transmissions
SENSITIVE_PATTERNS: tuple[str, ...] = (
    ".env",
    ".env.*",
    "*.env",
    "*.pem",
    "*.key",
    "*.pkcs12",
    "*.pfx",
    "id_rsa",
    "id_rsa.*",
    "id_ed25519",
    "id_ed25519.*",
    "*.secret",
    "credentials.json",
    "service_account*.json",
    "service-account*.json",
    "*service_account*.json",
    "*service-account*.json",
)

IGNORED_DIRECTORIES: set[str] = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "dist",
    "build",
    ".next",
    ".vite",
    ".idea",
    ".vscode",
}


@dataclass(frozen=True)
class GitStatus:
    """Snapshot of active git repository working tree state."""

    is_git: bool
    branch: str | None = None
    commit_sha: str | None = None
    commit_message: str | None = None
    is_dirty: bool = False
    staged_count: int = 0
    unstaged_count: int = 0
    untracked_count: int = 0
    raw_status: list[str] = field(default_factory=list)


def is_git_installed() -> bool:
    """Check if the git binary is available on system PATH."""
    return shutil.which("git") is not None


def find_git_root(start_path: Path | None = None) -> Path | None:
    """Traverse up the directory tree to locate the root of a Git repository."""
    current = (start_path or Path.cwd()).resolve()

    # Prefer native git rev-parse if git is installed
    if is_git_installed():
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=current,
                capture_output=True,
                text=True,
                check=False,
                timeout=3,
            )
            if result.returncode == 0:
                git_root = Path(result.stdout.strip()).resolve()
                if git_root.is_dir():
                    return git_root
        except (subprocess.SubprocessError, OSError):
            pass

    # Fallback filesystem traversal
    for path in [current, *current.parents]:
        if (path / ".git").exists():
            return path

    return None


def resolve_project_root(target_path: Path | str | None = None) -> Path:
    """Resolve the authoritative project root directory.

    If target_path is specified, resolves and verifies it.
    Otherwise detects git root, or falls back to current working directory.
    """
    if target_path:
        resolved = Path(target_path).resolve()
        if not resolved.exists():
            raise NexRepositoryError(
                f"Specified repository path does not exist: {target_path}",
                suggestion="Check the path provided via --path or cwd.",
            )
        if not resolved.is_dir():
            raise NexRepositoryError(
                f"Specified path is not a directory: {target_path}",
            )
        return resolved

    git_root = find_git_root()
    if git_root:
        return git_root

    return Path.cwd().resolve()


def resolve_within_repository(
    relative_or_abs_path: Path | str, repo_root: Path
) -> Path:
    """Safely resolve a target path within the repository boundary.

    Guards against:
    - Directory traversal (e.g. ../../etc/passwd)
    - Symlinks that resolve outside repo_root

    Raises NexPolicyViolationError if path escapes repository boundaries.
    """
    resolved_root = repo_root.resolve()
    target = (resolved_root / relative_or_abs_path).resolve()

    try:
        # relative_to will raise ValueError if target is not within resolved_root
        target.relative_to(resolved_root)
    except ValueError:
        raise NexPolicyViolationError(
            f"Path traversal detected: '{relative_or_abs_path}' resolves outside repository root '{resolved_root}'.",
            suggestion="Paths must remain strictly within the current repository workspace.",
        ) from None

    return target


def is_sensitive_path(path: Path) -> bool:
    """Check if a file matches sensitive credential or private key patterns."""
    name = path.name
    for pattern in SENSITIVE_PATTERNS:
        if fnmatch.fnmatch(name, pattern):
            return True
    return False


def get_git_status(repo_root: Path) -> GitStatus:
    """Inspect git working tree status cleanly without mutating anything."""
    if not is_git_installed() or not (repo_root / ".git").exists():
        return GitStatus(is_git=False)

    try:
        # Branch
        branch_res = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        branch = branch_res.stdout.strip() if branch_res.returncode == 0 else "HEAD"

        # Head Commit
        commit_res = subprocess.run(
            ["git", "log", "-1", "--format=%h %s"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        commit_sha = None
        commit_msg = None
        if commit_res.returncode == 0 and commit_res.stdout.strip():
            parts = commit_res.stdout.strip().split(" ", 1)
            commit_sha = parts[0]
            commit_msg = parts[1] if len(parts) > 1 else ""

        # Status porcelain
        status_res = subprocess.run(
            ["git", "status", "--porcelain=v1"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )

        staged_count = 0
        unstaged_count = 0
        untracked_count = 0
        raw_lines: list[str] = []

        if status_res.returncode == 0:
            for line in status_res.stdout.splitlines():
                if not line or len(line) < 3:
                    continue
                raw_lines.append(line)
                index_status = line[0]
                worktree_status = line[1]

                if index_status not in {" ", "?"}:
                    staged_count += 1
                if worktree_status not in {" ", "?"}:
                    unstaged_count += 1
                if index_status == "?" and worktree_status == "?":
                    untracked_count += 1

        is_dirty = (staged_count + unstaged_count + untracked_count) > 0

        return GitStatus(
            is_git=True,
            branch=branch,
            commit_sha=commit_sha,
            commit_message=commit_msg,
            is_dirty=is_dirty,
            staged_count=staged_count,
            unstaged_count=unstaged_count,
            untracked_count=untracked_count,
            raw_status=raw_lines,
        )

    except (subprocess.SubprocessError, OSError):
        return GitStatus(is_git=True, branch="unknown", is_dirty=False)


def collect_repository_summary(
    repo_root: Path, max_files: int = 5000
) -> dict[str, Any]:
    """Gather basic repository structural metadata without loading entire contents."""
    detected_languages: set[str] = set()
    total_files = 0
    total_bytes = 0
    config_files_found: list[str] = []

    extension_map = {
        ".py": "Python",
        ".js": "JavaScript",
        ".jsx": "React/JSX",
        ".ts": "TypeScript",
        ".tsx": "React/TSX",
        ".go": "Go",
        ".rs": "Rust",
        ".java": "Java",
        ".rb": "Ruby",
        ".php": "PHP",
        ".css": "CSS",
        ".html": "HTML",
        ".sh": "Shell",
    }

    key_manifests = {
        "pyproject.toml",
        "package.json",
        "Cargo.toml",
        "go.mod",
        "pom.xml",
        "docker-compose.yml",
        "Dockerfile",
    }

    try:
        for entry in repo_root.rglob("*"):
            if total_files >= max_files:
                break

            # Skip ignored directories
            parts = entry.parts
            if any(ignored in parts for ignored in IGNORED_DIRECTORIES):
                continue

            if entry.is_file():
                if is_sensitive_path(entry):
                    continue

                total_files += 1
                try:
                    total_bytes += entry.stat().st_size
                except OSError:
                    pass

                ext = entry.suffix.lower()
                if ext in extension_map:
                    detected_languages.add(extension_map[ext])

                if entry.name in key_manifests:
                    config_files_found.append(entry.name)

    except OSError:
        pass

    return {
        "root": str(repo_root),
        "name": repo_root.name,
        "total_files": total_files,
        "total_bytes": total_bytes,
        "languages": sorted(detected_languages),
        "manifests": sorted(set(config_files_found)),
    }


def scan_sensitive_files(repo_root: Path) -> list[dict[str, Any]]:
    """Scan repository for sensitive files, credentials, and private keys.

    Excludes ignored directories (.git, .venv, node_modules).
    """
    findings: list[dict[str, Any]] = []

    try:
        for entry in repo_root.rglob("*"):
            parts = entry.parts
            if any(ignored in parts for ignored in IGNORED_DIRECTORIES):
                continue

            if entry.is_file() and is_sensitive_path(entry):
                rel_path = str(entry.relative_to(repo_root))
                try:
                    stat_info = entry.stat()
                    size_bytes = stat_info.st_size
                    # Check if world readable (others read permission 0o004)
                    world_readable = bool(stat_info.st_mode & 0o004)
                    mode_octal = oct(stat_info.st_mode)[-3:]
                except OSError:
                    size_bytes = 0
                    world_readable = False
                    mode_octal = "unknown"

                matched_pattern = "sensitive_pattern"
                for p in SENSITIVE_PATTERNS:
                    if fnmatch.fnmatch(entry.name, p):
                        matched_pattern = p
                        break

                findings.append(
                    {
                        "path": rel_path,
                        "matched_pattern": matched_pattern,
                        "size_bytes": size_bytes,
                        "mode": mode_octal,
                        "world_readable": world_readable,
                    }
                )
    except OSError:
        pass

    return findings
