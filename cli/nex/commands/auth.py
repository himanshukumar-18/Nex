"""NEX CLI — Authentication Status, Whoami, and Logout Commands."""

import webbrowser
from typing import Annotated, Any

import typer
from rich.table import Table

from nex.client.django import NexDjangoClient
from nex.client.exceptions import NexClientAuthError, NexClientError
from nex.core.context import CLIContext
from nex.core.credentials import clear_credentials, get_stored_token
from nex.core.exceptions import NexError
from nex.core.exit_codes import ExitCode
from nex.output.json import print_json_success
from nex.output.terminal import console

app = typer.Typer(
    name="auth",
    help="Inspect, manage, and revoke active authentication credentials.",
    no_args_is_help=True,
)


@app.command(
    name="status", help="Display current authentication session and identity status."
)
def auth_status(ctx: typer.Context) -> None:
    """Verify and print authentication status."""
    cli_ctx: CLIContext = ctx.obj
    token = get_stored_token()

    if not token:
        if cli_ctx.json_mode:
            print_json_success(
                "auth.status",
                {
                    "authenticated": False,
                    "detail": "No credentials found in local vault.",
                },
                cli_ctx.correlation_id,
            )
        else:
            console.print()
            console.print("[bold #EF4444]✕ NOT AUTHENTICATED[/bold #EF4444]")
            console.print(
                "  [#A1A1B5]Run [bold #06B6D4]nex login[/bold #06B6D4] to authenticate with your NEX account.[/#A1A1B5]\n"
            )
        return

    # Verify token with backend
    backend_url = cli_ctx.config.api.base_url
    user_data: dict[str, Any] = {}
    try:
        with NexDjangoClient(base_url=backend_url, api_key=token) as client:
            user_data = client.request("GET", "/auth/me/")
    except NexClientAuthError as exc:
        clear_credentials()
        raise NexError(
            "Local session token has expired or been revoked by the server.",
            exit_code=ExitCode.AUTH_ERROR,
            suggestion="Run 'nex login' to establish a new authenticated session.",
        ) from exc
    except NexClientError as exc:
        raise NexError(
            f"Could not reach backend identity service: {exc.message}",
            exit_code=ExitCode.BACKEND_UNAVAILABLE,
        ) from exc

    if cli_ctx.json_mode:
        print_json_success(
            "auth.status",
            {
                "authenticated": True,
                "user": user_data,
            },
            cli_ctx.correlation_id,
        )
    else:
        console.print()
        table = Table(title="NEX Identity & Session Status", border_style="#6366F1")
        table.add_column("Property", style="#A1A1B5")
        table.add_column("Value", style="bold #F3F4F6")

        table.add_row("Status", "[bold #10B981]ACTIVE[/bold #10B981]")
        table.add_row("Email", user_data.get("email", "unknown"))
        table.add_row("Display Name", user_data.get("display_name") or "(not set)")
        table.add_row(
            "Role", f"[#F59E0B]{user_data.get('role', 'member').upper()}[/#F59E0B]"
        )
        table.add_row(
            "Email Verified",
            "✓ Yes" if user_data.get("email_verified") else "✗ Unverified",
        )
        table.add_row("Backend Gateway", backend_url)

        console.print(table)
        console.print()


@app.command(name="whoami", help="Display authenticated identity handle and role.")
def whoami(ctx: typer.Context) -> None:
    """Print authenticated user email and role."""
    cli_ctx: CLIContext = ctx.obj
    token = get_stored_token()

    if not token:
        raise NexError(
            "Not authenticated. Please run 'nex login' first.",
            exit_code=ExitCode.AUTH_ERROR,
            suggestion="Run 'nex login' to sign in via your web browser.",
        )

    backend_url = cli_ctx.config.api.base_url
    try:
        with NexDjangoClient(base_url=backend_url, api_key=token) as client:
            user_data = client.request("GET", "/auth/me/")
    except NexClientAuthError as exc:
        clear_credentials()
        raise NexError(
            "Authentication token has expired or been revoked.",
            exit_code=ExitCode.AUTH_ERROR,
            suggestion="Run 'nex login' to log in again.",
        ) from exc
    except NexClientError as exc:
        raise NexError(
            f"Failed to fetch profile: {exc.message}",
            exit_code=ExitCode.BACKEND_UNAVAILABLE,
        ) from exc

    if cli_ctx.json_mode:
        print_json_success("auth.whoami", user_data, cli_ctx.correlation_id)
    else:
        email = user_data.get("email")
        role = user_data.get("role", "member")
        console.print(
            f"[bold #06B6D4]{email}[/bold #06B6D4] ([#F59E0B]{role}[/#F59E0B])"
        )


@app.command(
    name="github",
    help="Inspect GitHub App authorization status or connect a GitHub account.",
)
def auth_github(
    ctx: typer.Context,
    connect: Annotated[
        bool,
        typer.Option(
            "--connect",
            "-c",
            help="Initiate GitHub App authorization and open the installation URL in the browser.",
        ),
    ] = False,
) -> None:
    """Inspect or initiate GitHub App authorization for the active NEX user."""
    cli_ctx: CLIContext = ctx.obj
    token = get_stored_token()

    if not token:
        raise NexError(
            "NEX authentication required. You must log in to NEX before managing GitHub authorization.",
            exit_code=ExitCode.AUTH_ERROR,
            suggestion="Run 'nex login' first.",
        )

    backend_url = cli_ctx.config.api.base_url

    # Handle connect request
    if connect:
        try:
            with NexDjangoClient(base_url=backend_url, api_key=token) as client:
                res = client.request("POST", "/repositories/github/install/")
                install_url = res.get("install_url")

                if not install_url:
                    raise NexError(
                        "Backend did not return a valid GitHub installation URL.",
                        exit_code=ExitCode.BACKEND_UNAVAILABLE,
                    )

                if cli_ctx.json_mode:
                    print_json_success(
                        "auth.github.connect",
                        {"install_url": install_url, "state": res.get("state")},
                        cli_ctx.correlation_id,
                    )
                    return

                console.print()
                console.print("[bold #8B5CF6]■ Opening GitHub App installation in your default browser...[/bold #8B5CF6]")
                console.print(f"  [dim]URL: {install_url}[/dim]\n")
                webbrowser.open(install_url)
                return
        except NexClientAuthError as exc:
            clear_credentials()
            raise NexError(
                "Local session has expired.",
                exit_code=ExitCode.AUTH_ERROR,
                suggestion="Run 'nex login' to re-authenticate.",
            ) from exc
        except NexClientError as exc:
            raise NexError(
                f"Failed to initiate GitHub authorization: {exc.message}",
                exit_code=ExitCode.BACKEND_UNAVAILABLE,
            ) from exc

    # Default: Inspect GitHub status
    try:
        with NexDjangoClient(base_url=backend_url, api_key=token) as client:
            status_data = client.request("GET", "/repositories/github/status/")
    except NexClientAuthError as exc:
        clear_credentials()
        raise NexError(
            "Local session has expired.",
            exit_code=ExitCode.AUTH_ERROR,
            suggestion="Run 'nex login' to re-authenticate.",
        ) from exc
    except NexClientError as exc:
        raise NexError(
            f"Failed to query GitHub status: {exc.message}",
            exit_code=ExitCode.BACKEND_UNAVAILABLE,
        ) from exc

    if cli_ctx.json_mode:
        print_json_success("auth.github", status_data, cli_ctx.correlation_id)
        return

    console.print()
    configured = status_data.get("configured", False)
    connected = status_data.get("connected", False)
    app_slug = status_data.get("app_slug", "nex-engineering-assistant")
    installations = status_data.get("installations", [])

    if not configured:
        console.print("[bold #F59E0B]▲ GITHUB APP NOT CONFIGURED ON BACKEND[/bold #F59E0B]")
        console.print(
            "  [#A1A1B5]Backend settings require GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY.[/#A1A1B5]\n"
        )
        return

    if not connected or not installations:
        console.print("[bold #00D9FF]■ GITHUB AUTHORIZATION: NOT CONNECTED[/bold #00D9FF]")
        console.print(
            f"  [#A1A1B5]No GitHub repositories authorized for your account with App '{app_slug}'.[/#A1A1B5]"
        )
        console.print(
            "  [#A1A1B5]Run [bold #8B5CF6]nex auth github --connect[/bold #8B5CF6] to authorize repositories in your browser.[/#A1A1B5]\n"
        )
        return

    table = Table(title=f"Authorized GitHub Installations ({app_slug})", border_style="#8B5CF6")
    table.add_column("Account Login", style="bold #00D9FF")
    table.add_column("Account Type", style="#A1A1B5")
    table.add_column("Installation ID", style="#F3F4F6")
    table.add_column("Scope", style="#A1A1B5")
    table.add_column("Status", style="bold #22C55E")

    for inst in installations:
        table.add_row(
            inst.get("account_login", "unknown"),
            inst.get("account_type", "User"),
            str(inst.get("installation_id", "")),
            inst.get("target_type", "selected"),
            inst.get("status", "active").upper(),
        )

    console.print(table)
    console.print()


def logout(ctx: typer.Context) -> None:
    """Sign out and revoke active CLI credentials."""
    cli_ctx: CLIContext = ctx.obj
    token = get_stored_token()

    if token:
        # Invalidate on backend
        backend_url = cli_ctx.config.api.base_url
        try:
            with NexDjangoClient(base_url=backend_url, api_key=token) as client:
                client.request("POST", "/auth/cli/revoke/")
        except Exception:
            # Backend revocation failure does not prevent local cleanup
            pass

    clear_credentials()

    if cli_ctx.json_mode:
        print_json_success("logout", {"status": "logged_out"}, cli_ctx.correlation_id)
    else:
        console.print()
        console.print("[bold #10B981]✓ Logged out successfully.[/bold #10B981]")
        console.print(
            "  [#A1A1B5]Local session credentials cleared from vault.[/#A1A1B5]\n"
        )
