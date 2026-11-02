"""Tests for repository discovery, path traversal defense, and sensitive files."""

from pathlib import Path

import pytest
from nex.core.exceptions import NexPolicyViolationError, NexRepositoryError
from nex.core.repository import (
    collect_repository_summary,
    is_sensitive_path,
    resolve_project_root,
    resolve_within_repository,
    scan_sensitive_files,
)


def test_resolve_project_root_default() -> None:
    """Ensure project root resolves to current workspace or git root."""
    root = resolve_project_root()
    assert root.exists()
    assert root.is_dir()


def test_resolve_project_root_non_existent(tmp_path: Path) -> None:
    """Ensure specifying a non-existent path raises NexRepositoryError."""
    fake_dir = tmp_path / "does_not_exist"
    with pytest.raises(NexRepositoryError):
        resolve_project_root(fake_dir)


def test_resolve_within_repository_safe(tmp_path: Path) -> None:
    """Test valid paths resolve correctly within repository boundaries."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subfile = repo / "src" / "app.py"
    subfile.parent.mkdir()
    subfile.touch()

    resolved = resolve_within_repository("src/app.py", repo)
    assert resolved == subfile.resolve()


def test_resolve_within_repository_path_traversal(tmp_path: Path) -> None:
    """Ensure path traversal outside repository raises NexPolicyViolationError."""
    repo = tmp_path / "repo"
    repo.mkdir()

    with pytest.raises(NexPolicyViolationError) as exc_info:
        resolve_within_repository("../../etc/passwd", repo)
    assert "Path traversal detected" in exc_info.value.message


def test_is_sensitive_path() -> None:
    """Ensure sensitive file patterns are properly detected."""
    sensitive_examples = [
        Path(".env"),
        Path(".env.local"),
        Path(".env.production"),
        Path("secret.pem"),
        Path("server.key"),
        Path("id_rsa"),
        Path("id_rsa.pub"),
        Path("id_ed25519"),
        Path("credentials.json"),
        Path("service_account_prod.json"),
    ]
    for p in sensitive_examples:
        assert is_sensitive_path(p), f"Expected {p} to be detected as sensitive"

    safe_examples = [
        Path("app.py"),
        Path("main.js"),
        Path("package.json"),
        Path("README.md"),
        Path("config.toml"),
    ]
    for p in safe_examples:
        assert not is_sensitive_path(p), f"Expected {p} to be safe"


def test_scan_sensitive_files(tmp_path: Path) -> None:
    """Ensure scan_sensitive_files discovers sensitive files and ignores .git/.venv."""
    repo = tmp_path / "test_repo"
    repo.mkdir()

    # Create sensitive files
    (repo / ".env").write_text("SECRET=123")
    (repo / "key.pem").write_text("CERT")

    # Create ignored directories with sensitive files that must be ignored
    git_dir = repo / ".git"
    git_dir.mkdir()
    (git_dir / "id_rsa").write_text("ignore")

    venv_dir = repo / ".venv"
    venv_dir.mkdir()
    (venv_dir / ".env").write_text("ignore")

    findings = scan_sensitive_files(repo)
    paths_found = [f["path"] for f in findings]

    assert ".env" in paths_found
    assert "key.pem" in paths_found
    assert not any(".git" in p for p in paths_found)
    assert not any(".venv" in p for p in paths_found)


def test_collect_repository_summary(tmp_path: Path) -> None:
    """Test structural repository inventory and language detection."""
    repo = tmp_path / "summary_repo"
    repo.mkdir()

    (repo / "main.py").write_text("print('hello')")
    (repo / "index.js").write_text("console.log('hi');")
    (repo / "package.json").write_text("{}")

    summary = collect_repository_summary(repo)
    assert summary["name"] == "summary_repo"
    assert summary["total_files"] == 3
    assert "Python" in summary["languages"]
    assert "JavaScript" in summary["languages"]
    assert "package.json" in summary["manifests"]
