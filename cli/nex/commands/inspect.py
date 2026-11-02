"""NEX Inspect Command.

Inspects local repository structure, git working tree status, languages,
and configuration metadata without modifying anything.
"""

from typing import Annotated

import typer

from nex.core.context import CLIContext
from nex.core.repository import collect_repository_summary, get_git_status
from nex.output.json import print_json_success

app = typer.Typer(help="Inspect local repository structure and git status.")


@app.callback(invoke_without_command=True)
def inspect(
    ctx: typer.Context,
    summary_only: Annotated[
        bool,
        typer.Option(
            "--summary", "-s", help="Display only high-level summary metadata."
        ),
    ] = False,
) -> None:
    """Inspect the current repository workspace, git status, and detected frameworks."""
    cli_ctx: CLIContext = ctx.obj
    repo_root = cli_ctx.repo_root

    git_info = get_git_status(repo_root)
    repo_summary = collect_repository_summary(repo_root)

    combined_data = {
        "repository": repo_summary,
        "git": {
            "is_git": git_info.is_git,
            "branch": git_info.branch,
            "commit": git_info.commit_sha,
            "message": git_info.commit_message,
            "is_dirty": git_info.is_dirty,
            "staged_files": git_info.staged_count,
            "unstaged_files": git_info.unstaged_count,
            "untracked_files": git_info.untracked_count,
        },
    }

    if cli_ctx.json_mode:
        print_json_success("inspect", combined_data, cli_ctx.correlation_id)
        return

    cli_ctx.output.print_banner("Repository Inspection", f"Root: {repo_root}")

    # Repository Summary Properties
    size_mb = f"{repo_summary['total_bytes'] / (1024 * 1024):.2f} MB"
    languages_str = (
        ", ".join(repo_summary["languages"]) if repo_summary["languages"] else "Unknown"
    )
    manifests_str = (
        ", ".join(repo_summary["manifests"]) if repo_summary["manifests"] else "None"
    )

    cli_ctx.output.print_key_value_pairs(
        "Workspace Metadata",
        [
            ("Project Name", repo_summary["name"]),
            ("Total Files", f"{repo_summary['total_files']} files"),
            ("Disk Footprint", size_mb),
            ("Detected Stacks", languages_str),
            ("Build Manifests", manifests_str),
        ],
    )

    # Git Status Section
    if git_info.is_git:
        dirty_label = (
            "[bold #F59E0B]DIRTY[/bold #F59E0B]"
            if git_info.is_dirty
            else "[bold #22C55E]CLEAN[/bold #22C55E]"
        )
        cli_ctx.output.print_key_value_pairs(
            "Version Control (Git)",
            [
                ("Active Branch", git_info.branch or "HEAD"),
                (
                    "Head Commit",
                    f"{git_info.commit_sha or 'none'} ({git_info.commit_message or ''})",
                ),
                ("Working Tree", dirty_label),
                ("Staged Changes", str(git_info.staged_count)),
                ("Unstaged Changes", str(git_info.unstaged_count)),
                ("Untracked Files", str(git_info.untracked_count)),
            ],
        )
    else:
        cli_ctx.output.print_warning("Current directory is not a Git repository.")

    cli_ctx.output.print_info("Inspection complete. Security boundaries respected.")
