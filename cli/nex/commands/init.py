"""NEX Init Command.

Initializes NEX project configuration and metadata in a repository.
"""

from typing import Annotated

import typer

from nex.config.loader import save_config_file
from nex.config.paths import get_project_config_path
from nex.config.schema import NexConfig
from nex.core.approvals import ApprovalPolicy, RiskLevel
from nex.core.context import CLIContext
from nex.output.json import print_json_success

app = typer.Typer(help="Initialize a new NEX project.")


@app.callback(invoke_without_command=True)
def init(
    ctx: typer.Context,
    name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="Project name override."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing project configuration."),
    ] = False,
) -> None:
    """Initialize a new NEX project configuration (.nex/config.toml)."""
    cli_ctx: CLIContext = ctx.obj
    repo_root = cli_ctx.repo_root
    config_path = get_project_config_path(repo_root)

    project_name = name or repo_root.name

    if config_path.exists() and not force:
        # Prompt approval to overwrite if not forced
        ApprovalPolicy.request_approval(
            f"Configuration already exists at {config_path}. Overwrite?",
            operation_name="init_overwrite",
            risk_level=RiskLevel.MEDIUM,
            yes_flag=cli_ctx.yes,
        )

    # Scaffolding default configuration
    default_config = NexConfig()
    default_config.project.name = project_name

    save_config_file(config_path, default_config.model_dump())

    if cli_ctx.json_mode:
        print_json_success(
            "init",
            {
                "project_name": project_name,
                "config_path": str(config_path),
                "initialized": True,
            },
            cli_ctx.correlation_id,
        )
    else:
        cli_ctx.output.print_banner(
            "Project Initialization", f"Repository: {repo_root.name}"
        )
        cli_ctx.output.print_success(f"Initialized project '{project_name}'")
        cli_ctx.output.print_info(f"Configuration written to: {config_path}")
        cli_ctx.output.print_info(
            "Workflow ready: Understand → Plan → Build → Verify → Ship"
        )
