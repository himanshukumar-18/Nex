"""NEX Command-Line Application Entry Point.

Production-grade CLI management and execution client for the NEX platform.
Core philosophy: Understand → Plan → Build → Verify → Ship
"""

import sys
from pathlib import Path
from typing import Annotated, Any

try:
    from click import ClickException  # type: ignore[import-not-found]
except ImportError:
    from typer._click.exceptions import ClickException  # type: ignore[no-redef]

import typer

from nex import __version__
from nex.commands.auth import app as auth_app
from nex.commands.auth import logout, whoami
from nex.commands.config import app as config_app
from nex.commands.fix import fix
from nex.commands.git import app as git_app
from nex.commands.init import init
from nex.commands.inspect import inspect
from nex.commands.login import login
from nex.commands.pr import app as pr_app
from nex.commands.repos import app as repos_app
from nex.commands.review import review
from nex.commands.runs import app as runs_app
from nex.commands.security import security
from nex.commands.test import test
from nex.config.loader import load_config
from nex.core.context import CLIContext
from nex.core.exceptions import NexError, NexInvalidInputError
from nex.core.exit_codes import ExitCode
from nex.core.repository import resolve_project_root
from nex.output.json import print_json_error, print_json_success
from nex.output.terminal import TerminalOutput, console, error_console


class NexTyper(typer.Typer):
    """Custom Typer application with unified error handling and POSIX exit code mappings."""

    @staticmethod
    def _normalize_args(argv: list[str]) -> list[str]:
        """Hoist global CLI options before subcommands for seamless developer ergonomics."""
        global_flags = {
            "--json",
            "--verbose",
            "-v",
            "--yes",
            "-y",
            "--no-color",
            "--version",
            "-V",
        }
        global_valued_flags = {"--path", "-p"}

        globals_found: list[str] = []
        rest: list[str] = []

        it = iter(argv)
        for arg in it:
            if arg in global_flags:
                globals_found.append(arg)
            elif arg in global_valued_flags:
                globals_found.append(arg)
                try:
                    globals_found.append(next(it))
                except StopIteration:
                    pass
            elif arg.startswith("--path=") or arg.startswith("-p="):
                globals_found.append(arg)
            else:
                rest.append(arg)

        return [*globals_found, *rest]

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        try:
            if args and isinstance(args[0], list):
                args = (self._normalize_args(list(args[0])), *args[1:])
            elif len(sys.argv) > 1:
                sys.argv = [sys.argv[0], *self._normalize_args(sys.argv[1:])]

            return super().__call__(*args, **kwargs)
        except NexError as err:
            is_json = "--json" in sys.argv
            command = "nex"
            for arg in sys.argv[1:]:
                if not arg.startswith("-"):
                    command = f"nex {arg}"
                    break

            if is_json:
                print_json_error(command, err)
            else:
                error_console.print(
                    f"[bold #EF4444]✕ ERROR:[/bold #EF4444] {err.message}"
                )
                if err.suggestion:
                    error_console.print(
                        f"  [#A1A1B5]Suggestion: {err.suggestion}[/#A1A1B5]"
                    )
            sys.exit(err.exit_code)
        except ClickException as err:
            if "--json" in sys.argv:
                print_json_error("cli", NexInvalidInputError(err.format_message()))
                sys.exit(ExitCode.INVALID_INPUT)
            raise
        except KeyboardInterrupt:
            if "--json" not in sys.argv:
                error_console.print("\n[dim]Operation cancelled by user.[/dim]")
            sys.exit(130)


app = NexTyper(
    name="nex",
    help="Autonomous Intelligence for Software Engineering — CLI Management Interface.",
    no_args_is_help=True,
    add_completion=False,
)


def is_json_requested() -> bool:
    """Check whether machine-readable JSON output was requested."""
    if "--json" in sys.argv:
        return True
    try:
        curr_frame: Any = sys._getframe(1)
        while curr_frame:
            for v in curr_frame.f_locals.values():
                if isinstance(v, (list, tuple)) and "--json" in v:
                    return True
            curr_frame = curr_frame.f_back
    except (ValueError, AttributeError):
        pass
    return False


def version_callback(value: bool) -> None:
    """Handle --version eager option."""
    if value:
        if is_json_requested():
            print_json_success("version", {"version": __version__, "platform": "nex"})
        else:
            console.print(
                f"[bold #00D9FF]■ NEX[/bold #00D9FF] [bold #8B5CF6]v{__version__}[/bold #8B5CF6] "
                "— Autonomous Intelligence for Software Engineering"
            )
        raise typer.Exit(code=0)


@app.callback()
def main_callback(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            help="Display NEX CLI version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose diagnostic output.",
        ),
    ] = False,
    json_mode: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Emit output as machine-readable JSON on stdout.",
        ),
    ] = False,
    path: Annotated[
        Path | None,
        typer.Option(
            "--path",
            "-p",
            help="Target repository directory path override.",
        ),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help="Automatically confirm low/medium risk operations.",
        ),
    ] = False,
    no_color: Annotated[
        bool,
        typer.Option(
            "--no-color",
            help="Disable ANSI color codes in terminal output.",
        ),
    ] = False,
) -> None:
    """NEX — Autonomous Intelligence for Software Engineering."""
    repo_root = resolve_project_root(path)

    cli_overrides: dict[str, Any] = {}
    if verbose:
        cli_overrides.setdefault("output", {})["verbose"] = True
    if no_color:
        cli_overrides.setdefault("output", {})["color"] = False

    config = load_config(repo_root, cli_overrides=cli_overrides)
    output = TerminalOutput(is_verbose=verbose, no_color=no_color)

    ctx.obj = CLIContext(
        config=config,
        output=output,
        repo_root=repo_root,
        verbose=verbose,
        json_mode=json_mode,
        yes=yes,
    )


# Register leaf commands
app.command(
    name="init", help="Initialize a new NEX project configuration (.nex/config.toml)."
)(init)
app.command(
    name="inspect",
    help="Inspect local repository structure, git status, and detected frameworks.",
)(inspect)
app.command(
    name="review", help="Analyze and review code changes in the active repository."
)(review)
app.command(name="fix", help="Plan and apply fixes for an issue or bug.")(fix)
app.command(
    name="test",
    help="Execute test suites respecting hybrid sandbox isolation policies.",
)(test)
app.command(
    name="security",
    help="Scan local repository workspace for credentials and sensitive files.",
)(security)
app.command(name="login", help="Authenticate with NEX via browser OAuth with PKCE.")(
    login
)
app.command(name="logout", help="Sign out and revoke active CLI credentials.")(logout)
app.command(name="whoami", help="Display currently authenticated NEX user profile.")(
    whoami
)

# Register command groups with subcommands
app.add_typer(auth_app, name="auth")
app.add_typer(config_app, name="config")
app.add_typer(git_app, name="git")
app.add_typer(pr_app, name="pr")
app.add_typer(repos_app, name="repos")
app.add_typer(runs_app, name="runs")


def main() -> None:
    """CLI script entrypoint."""
    app()


if __name__ == "__main__":
    main()
