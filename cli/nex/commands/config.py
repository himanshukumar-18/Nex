"""NEX Config Command.

Provides inspection and modification of user and project configuration layers
with secret redaction, schema validation, and safe permissions.
"""

from typing import Annotated, Any

import typer

from nex.config.loader import (
    load_config,
    read_toml_file,
    redact_secrets,
    save_config_file,
)
from nex.config.paths import get_project_config_path, get_user_config_path
from nex.core.context import CLIContext
from nex.core.exceptions import NexConfigError, NexInvalidInputError
from nex.output.json import print_json_success

app = typer.Typer(help="Inspect and modify NEX configuration settings.")


def _parse_value(val_str: str) -> Any:
    """Parse string value into appropriate primitive type."""
    lower = val_str.lower()
    if lower in {"true", "yes"}:
        return True
    if lower in {"false", "no"}:
        return False
    try:
        if "." in val_str:
            return float(val_str)
        return int(val_str)
    except ValueError:
        return val_str


def _get_nested_key(data: dict[str, Any], key_path: str) -> Any:
    """Traverse nested dictionary using dot notation."""
    parts = key_path.split(".")
    curr: Any = data
    for part in parts:
        if isinstance(curr, dict) and part in curr:
            curr = curr[part]
        else:
            raise NexConfigError(
                f"Configuration key '{key_path}' does not exist.",
                suggestion="Run 'nex config show' to view available keys.",
            )
    return curr


def _set_nested_key(data: dict[str, Any], key_path: str, value: Any) -> None:
    """Set a nested dictionary key using dot notation."""
    parts = key_path.split(".")
    curr = data
    for part in parts[:-1]:
        if part not in curr or not isinstance(curr[part], dict):
            curr[part] = {}
        curr = curr[part]
    curr[parts[-1]] = value


@app.command("show")
def show(ctx: typer.Context) -> None:
    """Show the active merged configuration with sensitive keys redacted."""
    cli_ctx: CLIContext = ctx.obj
    config_dict = cli_ctx.config.model_dump()
    redacted = redact_secrets(config_dict)

    if cli_ctx.json_mode:
        print_json_success("config show", redacted, cli_ctx.correlation_id)
        return

    cli_ctx.output.print_banner(
        "Active Configuration", f"Repo: {cli_ctx.repo_root.name}"
    )

    for section, values in redacted.items():
        if isinstance(values, dict):
            items = [(f"{section}.{k}", v) for k, v in values.items()]
            cli_ctx.output.print_key_value_pairs(section.upper(), items)


@app.command("path")
def path(ctx: typer.Context) -> None:
    """Display paths to project and user configuration files."""
    cli_ctx: CLIContext = ctx.obj
    user_p = get_user_config_path()
    proj_p = get_project_config_path(cli_ctx.repo_root)

    data = {
        "user_config": str(user_p),
        "user_config_exists": user_p.exists(),
        "project_config": str(proj_p),
        "project_config_exists": proj_p.exists(),
    }

    if cli_ctx.json_mode:
        print_json_success("config path", data, cli_ctx.correlation_id)
        return

    cli_ctx.output.print_banner("Configuration Paths")
    cli_ctx.output.print_key_value_pairs(
        "File Locations",
        [
            (
                "Project Config",
                f"{proj_p} ({'exists' if proj_p.exists() else 'missing'})",
            ),
            (
                "User Global Config",
                f"{user_p} ({'exists' if user_p.exists() else 'missing'})",
            ),
        ],
    )


@app.command("get")
def get(
    ctx: typer.Context,
    key: Annotated[
        str,
        typer.Argument(help="Configuration key in dot notation (e.g. api.base_url)."),
    ],
) -> None:
    """Get the value of a specific configuration key."""
    cli_ctx: CLIContext = ctx.obj
    config_dict = cli_ctx.config.model_dump()
    val = _get_nested_key(config_dict, key)

    # Redact if key is sensitive
    is_secret = any(
        s in key.lower() for s in ["api_key", "secret", "token", "password"]
    )
    display_val = (
        f"***{str(val)[-4:]}"
        if is_secret and isinstance(val, str) and len(val) > 4
        else ("***" if is_secret else val)
    )

    if cli_ctx.json_mode:
        print_json_success(
            "config get", {"key": key, "value": display_val}, cli_ctx.correlation_id
        )
        return

    cli_ctx.output.print_key_value_pairs("Configuration Key", [(key, display_val)])


@app.command("set")
def set_key(
    ctx: typer.Context,
    key: Annotated[
        str,
        typer.Argument(
            help="Configuration key in dot notation (e.g. general.default_model)."
        ),
    ],
    value: Annotated[str, typer.Argument(help="Value to assign.")],
    global_config: Annotated[
        bool,
        typer.Option(
            "--global",
            "-g",
            help="Write to user global configuration instead of project config.",
        ),
    ] = False,
) -> None:
    """Set a configuration key in project or user configuration."""
    cli_ctx: CLIContext = ctx.obj
    target_path = (
        get_user_config_path()
        if global_config
        else get_project_config_path(cli_ctx.repo_root)
    )

    parsed_value = _parse_value(value)
    existing_data = read_toml_file(target_path)
    _set_nested_key(existing_data, key, parsed_value)

    # Validate against schema
    try:
        load_config(cli_ctx.repo_root, cli_overrides=existing_data)
    except Exception as err:
        raise NexInvalidInputError(
            f"Invalid configuration value for '{key}': {err}",
            suggestion="Verify the value type expected by the configuration schema.",
        ) from err

    save_config_file(target_path, existing_data)

    if cli_ctx.json_mode:
        print_json_success(
            "config set",
            {"key": key, "value": parsed_value, "target_file": str(target_path)},
            cli_ctx.correlation_id,
        )
        return

    cli_ctx.output.print_success(f"Updated '{key}' = {parsed_value}")
    cli_ctx.output.print_info(f"Saved to: {target_path}")


@app.callback(invoke_without_command=True)
def default_callback(ctx: typer.Context) -> None:
    """Show configuration when invoked without subcommands."""
    if ctx.invoked_subcommand is None:
        show(ctx)
