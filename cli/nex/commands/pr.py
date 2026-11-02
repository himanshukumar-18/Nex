"""NEX Pull Request (PR) Command.

Prepares and submits pull requests for developer-approved changes.
Enforces CRITICAL-risk approval policies to ensure remote code publishing is explicitly consented.
"""

from typing import Annotated

import typer

from nex.core.approvals import ApprovalPolicy, RiskLevel
from nex.core.context import CLIContext
from nex.core.repository import get_git_status
from nex.output.json import print_json_success

app = typer.Typer(help="Create and manage GitHub pull requests.")


@app.callback(invoke_without_command=True)
def pr(
    ctx: typer.Context,
    title: Annotated[
        str | None,
        typer.Option("--title", "-t", help="Pull request title."),
    ] = None,
    body: Annotated[
        str | None,
        typer.Option("--body", "-b", help="Pull request description body."),
    ] = None,
    draft: Annotated[
        bool,
        typer.Option("--draft", "-d", help="Create PR as a draft."),
    ] = False,
    target_branch: Annotated[
        str,
        typer.Option("--target", help="Target branch to merge into."),
    ] = "main",
) -> None:
    """Prepare and publish a pull request to the remote repository."""
    cli_ctx: CLIContext = ctx.obj
    repo_root = cli_ctx.repo_root
    git_info = get_git_status(repo_root)

    current_branch = git_info.branch or "HEAD"
    pr_title = title or f"Changes from {current_branch}"

    # Creating a PR and pushing remote branches is a CRITICAL risk operation.
    # Automation flag --yes is strictly forbidden and rejected by ApprovalPolicy.
    ApprovalPolicy.request_approval(
        f"Publishing PR '{pr_title}' to remote branch '{target_branch}'. Proceed?",
        operation_name="create_pull_request",
        risk_level=RiskLevel.CRITICAL,
        yes_flag=cli_ctx.yes,
    )

    pr_data = {
        "title": pr_title,
        "body": body or "",
        "draft": draft,
        "source_branch": current_branch,
        "target_branch": target_branch,
        "approved": True,
        "risk_level": RiskLevel.CRITICAL.value,
        "message": (
            "Developer approval granted for pull request creation. Remote GitHub API "
            "integration is scheduled for subsequent Ship engine phase."
        ),
    }

    if cli_ctx.json_mode:
        print_json_success("pr", pr_data, cli_ctx.correlation_id)
        return

    cli_ctx.output.print_banner(
        "Pull Request (Ship)", f"Branch: {current_branch} → {target_branch}"
    )
    cli_ctx.output.print_success("Developer approval confirmed.")
    cli_ctx.output.print_key_value_pairs(
        "Pull Request Details",
        [
            ("Title", pr_title),
            ("Source Branch", current_branch),
            ("Target Branch", target_branch),
            ("Draft Mode", "Yes" if draft else "No"),
            ("Risk Level", "[bold #EF4444]CRITICAL[/bold #EF4444]"),
        ],
    )
    cli_ctx.output.print_info(
        "Remote GitHub repository connector and automated PR publisher will be "
        "orchestrated in the subsequent Ship phase."
    )
