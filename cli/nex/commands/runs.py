"""NEX Runs Command.

Inspects historical AI agent execution runs, task statuses, and metrics
by communicating with the Django backend API gateway.
"""

from typing import Annotated

import typer

from nex.client.exceptions import (
    NexClientAuthError,
    NexClientError,
    NexClientNetworkError,
    NexClientResponseError,
    NexClientTimeoutError,
)
from nex.core.context import CLIContext
from nex.core.exceptions import NexAuthError, NexBackendUnavailableError
from nex.output.json import print_json_success

app = typer.Typer(help="Inspect historical AI agent task runs and execution logs.")


@app.command("list")
def list_runs(
    ctx: typer.Context,
    limit: Annotated[
        int,
        typer.Option(
            "--limit", "-n", min=1, max=100, help="Maximum number of runs to display."
        ),
    ] = 10,
) -> None:
    """List recent AI task runs from the NEX backend."""
    cli_ctx: CLIContext = ctx.obj

    try:
        runs = cli_ctx.client.get_runs(limit=limit)
    except (NexClientNetworkError, NexClientTimeoutError) as err:
        raise NexBackendUnavailableError(
            f"Cannot connect to NEX backend at {cli_ctx.config.api.base_url}: {err}",
            suggestion="Ensure the NEX backend container is running (docker compose up -d nex-backend).",
        ) from err
    except NexClientAuthError as err:
        raise NexAuthError(
            f"Authentication failed querying runs: {err}",
            suggestion="Check your API key in ~/.nex/config.toml or NEX_API_KEY environment variable.",
        ) from err
    except NexClientResponseError as err:
        if err.status_code == 404:
            # Backend endpoint /runs/ is not yet deployed
            if cli_ctx.json_mode:
                print_json_success(
                    "runs list",
                    {
                        "runs": [],
                        "total": 0,
                        "status": "endpoint_pending",
                        "message": "Runs endpoint is scheduled for subsequent backend integration phase.",
                    },
                    cli_ctx.correlation_id,
                )
                return
            cli_ctx.output.print_banner("Agent Task Runs")
            cli_ctx.output.print_info(
                "Backend endpoint '/api/v1/runs/' is not yet registered. "
                "Task runs will be populated once agent workflows execute."
            )
            return
        raise NexBackendUnavailableError(f"Backend returned error: {err}") from err
    except NexClientError as err:
        raise NexBackendUnavailableError(f"Client communication error: {err}") from err

    if cli_ctx.json_mode:
        print_json_success(
            "runs list", {"runs": runs, "total": len(runs)}, cli_ctx.correlation_id
        )
        return

    cli_ctx.output.print_banner("Agent Task Runs", f"Limit: {limit}")

    if not runs:
        cli_ctx.output.print_info(
            "No recent task runs recorded. Start a new workflow with 'nex fix' or 'nex inspect'."
        )
        return

    table_rows = []
    for r in runs:
        run_id = str(r.get("id", "unknown"))[:8]
        task_type = str(r.get("task_type", "general"))
        status = str(r.get("status", "unknown"))
        duration = f"{r.get('duration_ms', 0)}ms" if r.get("duration_ms") else "-"
        created_at = str(r.get("created_at", "-"))
        table_rows.append([run_id, task_type, status, duration, created_at])

    cli_ctx.output.print_table(
        "Recent Task Runs",
        ["Run ID", "Task Type", "Status", "Duration", "Created At"],
        table_rows,
    )


@app.command("get")
def get_run(
    ctx: typer.Context,
    run_id: Annotated[str, typer.Argument(help="UUID or identifier of the task run.")],
) -> None:
    """Retrieve detailed execution telemetry for a specific task run."""
    cli_ctx: CLIContext = ctx.obj

    try:
        run_data = cli_ctx.client.get_run(run_id)
    except (NexClientNetworkError, NexClientTimeoutError) as err:
        raise NexBackendUnavailableError(
            f"Cannot connect to NEX backend at {cli_ctx.config.api.base_url}: {err}",
            suggestion="Ensure the NEX backend container is running.",
        ) from err
    except NexClientAuthError as err:
        raise NexAuthError(
            f"Authentication failed querying run '{run_id}': {err}",
        ) from err
    except NexClientResponseError as err:
        if err.status_code == 404:
            if cli_ctx.json_mode:
                print_json_success(
                    "runs get",
                    {
                        "run_id": run_id,
                        "found": False,
                        "message": f"Run '{run_id}' not found.",
                    },
                    cli_ctx.correlation_id,
                )
                return
            cli_ctx.output.print_warning(
                f"Task run '{run_id}' was not found on backend."
            )
            return
        raise NexBackendUnavailableError(f"Backend returned error: {err}") from err
    except NexClientError as err:
        raise NexBackendUnavailableError(
            f"Client communication failure: {err}"
        ) from err

    if cli_ctx.json_mode:
        print_json_success("runs get", run_data, cli_ctx.correlation_id)
        return

    cli_ctx.output.print_banner("Task Run Details", f"ID: {run_id}")
    items = [(k, v) for k, v in run_data.items() if not isinstance(v, (dict, list))]
    cli_ctx.output.print_key_value_pairs("Run Attributes", items)


@app.callback(invoke_without_command=True)
def default_callback(ctx: typer.Context) -> None:
    """List runs by default when invoked without subcommands."""
    if ctx.invoked_subcommand is None:
        list_runs(ctx)
