"""NEX Configuration Loader & Serialization.

Loads, merges, and validates configuration layers across CLI options,
environment variables, project files, and user global settings with strict priority.
"""

import os
import tomllib
from pathlib import Path
from typing import Any

import tomli_w

from nex.config.paths import get_project_config_path, get_user_config_path
from nex.config.schema import NexConfig
from nex.core.exceptions import NexConfigError

# Sensitive keys that must be redacted when displaying configuration
SECRET_KEYS = {
    "api_key",
    "secret",
    "token",
    "password",
    "credential",
    "private_key",
    "internal_service_secret",
}


def redact_secrets(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively mask sensitive values to prevent terminal or log leakage."""
    redacted: dict[str, Any] = {}
    for key, value in data.items():
        lower_key = key.lower()
        if (
            any(secret in lower_key for secret in SECRET_KEYS)
            and isinstance(value, str)
            and value
        ):
            redacted[key] = f"***{value[-4:]}" if len(value) > 4 else "***"
        elif isinstance(value, dict):
            redacted[key] = redact_secrets(value)
        else:
            redacted[key] = value
    return redacted


def read_toml_file(path: Path) -> dict[str, Any]:
    """Safely parse a TOML configuration file if it exists."""
    if not path.exists() or not path.is_file():
        return {}

    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as err:
        raise NexConfigError(
            f"Failed to parse TOML configuration at {path}: {err}",
            suggestion="Check the file syntax and ensure it is valid TOML.",
        ) from err
    except OSError as err:
        raise NexConfigError(
            f"Failed to read configuration file at {path}: {err}",
        ) from err


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries, overriding base with values from override."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        elif value is not None:
            result[key] = value
    return result


def load_config(
    repo_root: Path | None = None,
    *,
    cli_overrides: dict[str, Any] | None = None,
) -> NexConfig:
    """Load and merge configuration layers in strict precedence order.

    Priority:
    1. Explicit CLI options
    2. Environment variables (NEX_*)
    3. Project configuration (<repo_root>/.nex/config.toml or nex.toml)
    4. User global configuration (~/.nex/config.toml)
    5. Default schema values
    """
    merged: dict[str, Any] = {}

    # 4. User Global Configuration
    user_path = get_user_config_path()
    user_data = read_toml_file(user_path)
    merged = deep_merge(merged, user_data)

    # 3. Project Configuration (if within a repository)
    if repo_root:
        project_path = get_project_config_path(repo_root)
        project_data = read_toml_file(project_path)
        merged = deep_merge(merged, project_data)

    # 2. Environment Variables
    env_data: dict[str, Any] = {}
    if "NEX_API_URL" in os.environ:
        env_data.setdefault("api", {})["base_url"] = os.environ["NEX_API_URL"]
    if "NEX_DEFAULT_MODEL" in os.environ:
        env_data.setdefault("general", {})["default_model"] = os.environ[
            "NEX_DEFAULT_MODEL"
        ]
    if "NEX_DEFAULT_PROVIDER" in os.environ:
        env_data.setdefault("general", {})["default_provider"] = os.environ[
            "NEX_DEFAULT_PROVIDER"
        ]
    if "NEX_VERBOSE" in os.environ:
        env_data.setdefault("output", {})["verbose"] = os.environ[
            "NEX_VERBOSE"
        ].lower() in {"1", "true", "yes"}
    if "NEX_REQUIRE_APPROVAL" in os.environ:
        env_data.setdefault("execution", {})["require_approval"] = os.environ[
            "NEX_REQUIRE_APPROVAL"
        ].lower() in {"1", "true", "yes"}

    merged = deep_merge(merged, env_data)

    # 1. CLI Overrides
    if cli_overrides:
        merged = deep_merge(merged, cli_overrides)

    try:
        return NexConfig.model_validate(merged)
    except Exception as err:
        raise NexConfigError(
            f"Configuration schema validation failed: {err}",
            suggestion="Verify configuration keys and data types.",
        ) from err


def _clean_nones(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively strip None values since TOML does not support null/None."""
    clean: dict[str, Any] = {}
    for k, v in data.items():
        if v is None:
            continue
        if isinstance(v, dict):
            clean[k] = _clean_nones(v)
        else:
            clean[k] = v
    return clean


def save_config_file(path: Path, config_dict: dict[str, Any]) -> None:
    """Write configuration dictionary to TOML with secure permissions (0o600)."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        cleaned = _clean_nones(config_dict)
        toml_content = tomli_w.dumps(cleaned)

        # Write file with restrictive permissions
        with open(path, "w", encoding="utf-8") as f:
            f.write(toml_content)

        # Restrict permissions to owner read/write on Unix
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    except OSError as err:
        raise NexConfigError(
            f"Failed to write configuration file at {path}: {err}",
        ) from err
