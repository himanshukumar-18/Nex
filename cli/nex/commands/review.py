"""NEX Review Command.

Inspects local staged or working-tree code changes for review.
Integrates with git status and prepares review payloads for the NEX agent review engine.
"""

from typing import Annotated

import typer

from nex.core.context import CLIContext
from nex.core.repository import get_git_status
from nex.output.json import print_json_success

app = typer.Typer(help="Review code changes in working tree or staged commits.")


@app.callback(invoke_without_command=True)
def review(
    ctx: typer.Context,
    staged: Annotated[
        bool,
        typer.Option("--staged", "-s", help="Inspect only staged git changes."),
    ] = False,
) -> None:
    """Analyze and review code changes in the active repository."""
    cli_ctx: CLIContext = ctx.obj
    repo_root = cli_ctx.repo_root

    git_info = get_git_status(repo_root)

    if not git_info.is_git:
        if cli_ctx.json_mode:
            print_json_success(
                "review",
                {
                    "is_git": False,
                    "staged_only": staged,
                    "changes": [],
                    "message": "Directory is not a Git repository. Local diff inspection skipped.",
                },
                cli_ctx.correlation_id,
            )
        else:
            cli_ctx.output.print_banner("Code Review", f"Workspace: {repo_root.name}")
            cli_ctx.output.print_warning(
                "Directory is not a Git repository. Cannot perform git diff review."
            )
        return

    # Filter changed files based on staged flag
    relevant_files: list[dict[str, str]] = []
    for line in git_info.raw_status:
        if len(line) < 3:
            continue
        index_status = line[0]
        worktree_status = line[1]
        file_path = line[3:].strip()

        if staged:
            if index_status not in {" ", "?"}:
                relevant_files.append(
                    {"status": index_status, "file": file_path, "type": "staged"}
                )
        else:
            status_desc = "untracked" if index_status == "?" else "modified"
            relevant_files.append(
                {
                    "status": f"{index_status}{worktree_status}".strip(),
                    "file": file_path,
                    "type": status_desc,
                }
            )

    result_data = {
        "staged_only": staged,
        "branch": git_info.branch,
        "commit": git_info.commit_sha,
        "total_changes": len(relevant_files),
        "changes": relevant_files,
        "engine_status": "ready_for_agent_runtime",
        "message": (
            "Autonomous AI code review engine is scheduled for future agent-runtime release. "
            "Local diff inspection completed successfully."
        ),
    }

    if cli_ctx.json_mode:
        print_json_success("review", result_data, cli_ctx.correlation_id)
        return

    cli_ctx.output.print_banner("Code Review", f"Branch: {git_info.branch or 'HEAD'}")

    if not relevant_files:
        target_desc = "staged changes" if staged else "working tree changes"
        cli_ctx.output.print_success(f"No {target_desc} detected. Working tree clean.")
        return

    target_title = "Staged Changes" if staged else "Uncommitted Working Tree Changes"
    cli_ctx.output.print_table(
        target_title,
        ["Status", "Type", "File Path"],
        [[item["status"], item["type"], item["file"]] for item in relevant_files],
    )

    cli_ctx.output.print_info(
        "Local diff analysis complete. Autonomous AI code review workflows will be "
        "orchestrated in the subsequent agent-runtime execution phase."
    )
