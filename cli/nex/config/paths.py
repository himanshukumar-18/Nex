"""NEX Configuration & Directory Path Resolution.

Resolves platform-appropriate directories for global user settings,
project-level configurations, and temporary local metadata.
"""

from pathlib import Path


def get_user_config_dir() -> Path:
    """Return user-level global configuration directory (~/.nex)."""
    return (Path.home() / ".nex").resolve()


def get_user_config_path() -> Path:
    """Return path to global user configuration file (~/.nex/config.toml)."""
    return get_user_config_dir() / "config.toml"


def get_project_config_dir(repo_root: Path) -> Path:
    """Return project-level metadata directory (<repo_root>/.nex)."""
    return (repo_root / ".nex").resolve()


def get_project_config_path(repo_root: Path) -> Path:
    """Return path to project configuration file (<repo_root>/.nex/config.toml or nex.toml)."""
    # Check for root nex.toml first, then .nex/config.toml
    root_toml = repo_root / "nex.toml"
    if root_toml.exists() and root_toml.is_file():
        return root_toml.resolve()

    return get_project_config_dir(repo_root) / "config.toml"
