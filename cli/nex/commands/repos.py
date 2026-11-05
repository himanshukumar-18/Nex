"""NEX CLI — GitHub Repository Management & Discovery Commands.

Lists, inspects, and synchronizes repositories discovered via the authorized GitHub App.
"""

from __future__ import annotations

import re
from typing import Annotated, Any

import typer
from rich import box
from rich.panel import Panel
from rich.table import Table

from nex.client.exceptions import NexClientAuthError, NexClientError
from nex.core.context import CLIContext
from nex.core.credentials import clear_credentials, get_stored_token
from nex.core.exceptions import NexError
from nex.core.exit_codes import ExitCode
from nex.output.json import print_json_success
from nex.output.terminal import console

app = typer.Typer(
    name="repos",
    help="Discover, inspect, and synchronize GitHub repositories.",
    no_args_is_help=True,
)

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


def _require_auth() -> str:
    """Ensure user is authenticated before performing remote operations."""
    token = get_stored_token()
    if not token:
        raise NexError(
            "Not authenticated. Please run 'nex login' first.",
            exit_code=ExitCode.AUTH_ERROR,
            suggestion="Run 'nex login' to sign in via your web browser.",
        )
    return token


@app.command(name="list")
def list_repositories(
    ctx: typer.Context,
    search: Annotated[
        str | None,
        typer.Option("--search", "-s", help="Filter repositories by name or description."),
    ] = None,
    visibility: Annotated[
        str | None,
        typer.Option(
            "--visibility",
            "-v",
            help="Filter by visibility: 'public' or 'private'.",
        ),
    ] = None,
    language: Annotated[
        str | None,
        typer.Option("--language", "-l", help="Filter by programming language."),
    ] = None,
    show_all: Annotated[
        bool,
        typer.Option("--all", "-a", help="Include unlinked/removed repositories."),
    ] = False,
) -> None:
    """List GitHub repositories synchronized with NEX."""
    cli_ctx: CLIContext = ctx.obj
    _require_auth()

    params: dict[str, Any] = {"page_size": 100}
    if search:
        params["search"] = search
    if visibility:
        params["visibility"] = visibility.lower()
    if language:
        params["language"] = language
    params["status"] = "all" if show_all else "active"

    try:
        res = cli_ctx.client.request("GET", "/repositories/", params=params)
        repos = res.get("results", []) if isinstance(res, dict) else res
    except NexClientAuthError as exc:
        clear_credentials()
        raise NexError(
            "Authentication token has expired or been revoked.",
            exit_code=ExitCode.AUTH_ERROR,
            suggestion="Run 'nex login' to log in again.",
        ) from exc
    except NexClientError as exc:
        raise NexError(
            f"Failed to fetch repositories: {exc.message}",
            exit_code=ExitCode.BACKEND_UNAVAILABLE,
        ) from exc

    if cli_ctx.json_mode:
        print_json_success(
            "repos.list",
            {"count": len(repos), "repositories": repos},
            cli_ctx.correlation_id,
        )
        return

    console.print()
    if not repos:
        console.print("[#A1A1B5]No repositories found matching query.[/#A1A1B5]")
        console.print(
            "  [dim]Run 'nex repos sync' to discover repositories from your GitHub account.[/dim]\n"
        )
        return

    table = Table(
        title="[bold #00D9FF]SYNCHRONIZED GITHUB REPOSITORIES[/bold #00D9FF]",
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold #A1A1B5",
    )
    table.add_column("Repository", style="bold #F1F1F5")
    table.add_column("Visibility", justify="center")
    table.add_column("Branch", style="dim")
    table.add_column("Language", style="#F59E0B")
    table.add_column("Status", justify="center")

    for repo in repos:
        full_name = repo.get("full_name", repo.get("name", "unknown"))
        is_priv = repo.get("is_private", False)
        vis_tag = "[#8B5CF6]PRIVATE[/#8B5CF6]" if is_priv else "[#00D9FF]PUBLIC[/#00D9FF]"
        branch = repo.get("default_branch", "main")
        lang = repo.get("language") or "-"
        sync_status = repo.get("sync_status", "synced").upper()
        status_tag = (
            f"[#10B981]{sync_status}[/#10B981]"
            if sync_status == "SYNCED"
            else f"[#EF4444]{sync_status}[/#EF4444]"
        )

        table.add_row(full_name, vis_tag, branch, lang, status_tag)

    console.print(table)
    console.print(f"  [dim]Total: {len(repos)} repositories displayed.[/dim]\n")


@app.command(name="sync")
def sync_repositories(
    ctx: typer.Context,
    installation_id: Annotated[
        int | None,
        typer.Option(
            "--installation-id",
            "-i",
            help="Specific GitHub installation ID to synchronize.",
        ),
    ] = None,
) -> None:
    """Trigger synchronization of repositories from GitHub App installations."""
    cli_ctx: CLIContext = ctx.obj
    _require_auth()

    payload: dict[str, Any] = {}
    if installation_id:
        payload["installation_id"] = installation_id

    try:
        res = cli_ctx.client.request("POST", "/repositories/sync/", json=payload)
    except NexClientAuthError as exc:
        clear_credentials()
        raise NexError(
            "Authentication token has expired or been revoked.",
            exit_code=ExitCode.AUTH_ERROR,
            suggestion="Run 'nex login' to log in again.",
        ) from exc
    except NexClientError as exc:
        raise NexError(
            f"Failed to synchronize repositories: {exc.message}",
            exit_code=ExitCode.BACKEND_UNAVAILABLE,
        ) from exc

    if cli_ctx.json_mode:
        print_json_success("repos.sync", res, cli_ctx.correlation_id)
        return

    console.print()
    total = res.get("total", 0)
    added = res.get("added", 0)
    updated = res.get("updated", 0)
    removed = res.get("removed", 0)
    inst_synced = res.get("installations_synced", 0)

    console.print(
        "[bold #10B981]✓ Repositories synchronized successfully[/bold #10B981]"
    )
    console.print(f"  • Total accessible:     [bold #F1F1F5]{total}[/bold #F1F1F5]")
    console.print(f"  • Added:                [bold #10B981]{added}[/bold #10B981]")
    console.print(f"  • Updated:              [bold #00D9FF]{updated}[/bold #00D9FF]")
    console.print(f"  • Removed/Archived:     [bold #EF4444]{removed}[/bold #EF4444]")
    console.print(f"  • Installations synced: [bold #F59E0B]{inst_synced}[/bold #F59E0B]\n")


@app.command(name="show")
def show_repository(
    ctx: typer.Context,
    identifier: Annotated[
        str,
        typer.Argument(
            help="Repository UUID, GitHub numeric ID, or repository slug (owner/name)."
        ),
    ],
) -> None:
    """Inspect detailed metadata and clone URLs for a synchronized repository."""
    cli_ctx: CLIContext = ctx.obj
    _require_auth()

    repo_id: str | None = None

    if UUID_PATTERN.match(identifier.strip()):
        repo_id = identifier.strip()
    else:
        # Resolve identifier by searching
        try:
            res = cli_ctx.client.request(
                "GET", "/repositories/", params={"search": identifier, "page_size": 10}
            )
            candidates = res.get("results", []) if isinstance(res, dict) else res
            for cand in candidates:
                if (
                    cand.get("full_name", "").lower() == identifier.lower()
                    or cand.get("name", "").lower() == identifier.lower()
                    or str(cand.get("github_repo_id")) == identifier
                ):
                    repo_id = cand.get("id")
                    break

            if not repo_id and candidates:
                repo_id = candidates[0].get("id")
        except NexClientError as exc:
            raise NexError(
                f"Failed to lookup repository '{identifier}': {exc.message}",
                exit_code=ExitCode.BACKEND_UNAVAILABLE,
            ) from exc

    if not repo_id:
        raise NexError(
            f"Repository '{identifier}' was not found.",
            exit_code=ExitCode.INVALID_INPUT,
            suggestion="Run 'nex repos list' to see all synchronized repositories.",
        )

    try:
        repo_data = cli_ctx.client.request("GET", f"/repositories/{repo_id}/")
    except NexClientAuthError as exc:
        clear_credentials()
        raise NexError(
            "Authentication token has expired or been revoked.",
            exit_code=ExitCode.AUTH_ERROR,
            suggestion="Run 'nex login' to log in again.",
        ) from exc
    except NexClientError as exc:
        raise NexError(
            f"Failed to fetch repository details: {exc.message}",
            exit_code=ExitCode.BACKEND_UNAVAILABLE,
        ) from exc

    if cli_ctx.json_mode:
        print_json_success("repos.show", repo_data, cli_ctx.correlation_id)
        return

    console.print()
    full_name = repo_data.get("full_name", "unknown")
    desc = repo_data.get("description") or "No description provided."
    is_priv = repo_data.get("is_private", False)
    vis = "[#8B5CF6]PRIVATE[/#8B5CF6]" if is_priv else "[#00D9FF]PUBLIC[/#00D9FF]"
    branch = repo_data.get("default_branch", "main")
    lang = repo_data.get("language") or "None"
    clone_url = repo_data.get("clone_url") or f"https://github.com/{full_name}.git"
    ssh_url = repo_data.get("ssh_url") or f"git@github.com:{full_name}.git"
    html_url = repo_data.get("html_url") or f"https://github.com/{full_name}"
    sync_status = repo_data.get("sync_status", "synced").upper()

    content = f"""[bold #00D9FF]{full_name}[/bold #00D9FF] ({vis})
[#A1A1B5]{desc}[/#A1A1B5]

[bold #A1A1B5]METADATA[/bold #A1A1B5]
  • Default Branch:  [bold #F1F1F5]{branch}[/bold #F1F1F5]
  • Language:        [bold #F59E0B]{lang}[/bold #F59E0B]
  • Status:          [bold #10B981]{sync_status}[/bold #10B981]
  • Web URL:         [link={html_url}]{html_url}[/link]

[bold #A1A1B5]CLONE URLS[/bold #A1A1B5]
  • HTTPS:           [#00D9FF]{clone_url}[/#00D9FF]
  • SSH:             [#8B5CF6]{ssh_url}[/#8B5CF6]
"""

    panel = Panel(
        content.strip(),
        title="[bold #F1F1F5]REPOSITORY DETAILS[/bold #F1F1F5]",
        border_style="#3B82F6",
        padding=(1, 2),
    )
    console.print(panel)
    console.print()
