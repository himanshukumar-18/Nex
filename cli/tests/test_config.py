"""Tests for configuration loader, schema validation, and secret redaction."""

from pathlib import Path

import pytest
from nex.config.loader import (
    deep_merge,
    load_config,
    read_toml_file,
    redact_secrets,
    save_config_file,
)
from nex.core.exceptions import NexConfigError


def test_redact_secrets_masks_sensitive_keys() -> None:
    """Ensure API keys and credentials are recursively masked."""
    config_data = {
        "general": {"default_model": "gemini-2.0-flash"},
        "api": {
            "base_url": "http://localhost:8080/api/v1",
            "api_key": "sk-secret-1234567890",
        },
        "auth": {
            "token": "bearer-token-abc",
            "db_password": "supersecretpassword",
        },
    }

    redacted = redact_secrets(config_data)
    assert redacted["general"]["default_model"] == "gemini-2.0-flash"
    assert redacted["api"]["base_url"] == "http://localhost:8080/api/v1"
    assert redacted["api"]["api_key"].startswith("***")
    assert "1234567890" not in redacted["api"]["api_key"]
    assert redacted["auth"]["token"].startswith("***")
    assert redacted["auth"]["db_password"].startswith("***")


def test_save_and_read_toml_file(tmp_path: Path) -> None:
    """Test serializing to TOML and reading it back."""
    target_file = tmp_path / "config.toml"
    data = {
        "general": {"default_model": "test-model"},
        "api": {"timeout_seconds": 30.0},
    }

    save_config_file(target_file, data)
    assert target_file.exists()

    loaded = read_toml_file(target_file)
    assert loaded["general"]["default_model"] == "test-model"
    assert loaded["api"]["timeout_seconds"] == 30.0


def test_deep_merge() -> None:
    """Verify recursive dictionary merging."""
    base = {"a": 1, "b": {"x": 10, "y": 20}}
    override = {"b": {"y": 99, "z": 30}, "c": 3}
    merged = deep_merge(base, override)

    assert merged == {"a": 1, "b": {"x": 10, "y": 99, "z": 30}, "c": 3}


def test_load_config_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensure environment variables override project config and defaults."""
    repo = tmp_path / "test_repo"
    repo.mkdir()
    project_nex = repo / ".nex"
    project_nex.mkdir()
    project_config = project_nex / "config.toml"

    # Write project config
    save_config_file(
        project_config, {"api": {"base_url": "http://project-host/api/v1"}}
    )

    # Set environment variable
    monkeypatch.setenv("NEX_API_URL", "http://env-host/api/v1")

    # Load config
    cfg = load_config(repo)
    assert cfg.api.base_url == "http://env-host/api/v1"

    # Now verify explicit CLI override has top priority
    cfg_cli = load_config(
        repo, cli_overrides={"api": {"base_url": "http://cli-host/api/v1"}}
    )
    assert cfg_cli.api.base_url == "http://cli-host/api/v1"


def test_load_config_invalid_schema(tmp_path: Path) -> None:
    """Ensure invalid schema types raise NexConfigError."""
    repo = tmp_path / "bad_repo"
    repo.mkdir()
    project_nex = repo / ".nex"
    project_nex.mkdir()
    project_config = project_nex / "config.toml"

    # timeout_seconds should be float/int, not a string that cannot convert
    save_config_file(project_config, {"api": {"timeout_seconds": "not_a_number"}})

    with pytest.raises(NexConfigError) as exc_info:
        load_config(repo)
    assert "Configuration schema validation failed" in exc_info.value.message
