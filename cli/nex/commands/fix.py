"""NEX Fix Command.

Plans and applies targeted fixes for reported issues or tasks.
Enforces HIGH-risk approval policies to ensure safe code modification boundaries.
"""

from typing import Annotated

import typer

from nex.core.approvals import ApprovalPolicy, RiskLevel
from nex.core.context import CLIContext
from nex.output.json import print_json_success

app = typer.Typer(help="Plan and apply fixes for an issue or bug.")


@app.callback(invoke_without_command=True)
def fix(
    ctx: typer.Context,
    issue: Annotated[
        str,
        typer.Argument(help="Issue description, ticket ID, or bug summary to fix."),
    ],
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", "-d", help="Preview planned fix without modifying code."
        ),
    ] = False,
) -> None:
    """Analyze an issue and coordinate code generation through the NEX Build engine."""
    cli_ctx: CLIContext = ctx.obj

    # Dry-run is a safe preview (MEDIUM risk if approval needed, or preview directly)
    if dry_run:
        fix_plan = {
            "issue": issue,
            "mode": "dry-run",
            "risk_level": RiskLevel.LOW.value,
            "planned_actions": [
                "1. Repository inspection and AST context gathering (Understand)",
                "2. Targeted patch generation in isolated sandbox (Plan & Build)",
                "3. Automated test verification (Verify)",
                "4. Local working tree diff presentation (Ship)",
            ],
            "message": (
                "Dry-run preview: No code modifications were performed. "
                "Autonomous code generation engine is scheduled for subsequent agent-runtime release."
            ),
        }
        if cli_ctx.json_mode:
            print_json_success("fix", fix_plan, cli_ctx.correlation_id)
            return

        cli_ctx.output.print_banner("Issue Fix Plan (Dry-Run)", f"Issue: {issue}")
        cli_ctx.output.print_info("Execution Mode: DRY-RUN (read-only preview)")
        cli_ctx.output.print_table(
            "Planned Agent Execution Stages",
            ["Stage", "Action", "Target"],
            [
                [
                    "Understand",
                    "Analyze repository structure and affected symbols",
                    "Local Repository",
                ],
                [
                    "Plan",
                    "Construct deterministic patch specification",
                    "Agent Runtime",
                ],
                ["Build", "Generate candidate code modification", "Isolated Sandbox"],
                ["Verify", "Execute regression test suite", "Isolated Sandbox"],
                ["Ship", "Stage changes for developer review", "Local Working Tree"],
            ],
        )
        cli_ctx.output.print_success(
            "Dry-run preview completed. To apply, run without --dry-run."
        )
        return

    # Non-dry-run is a HIGH risk operation requiring developer approval
    ApprovalPolicy.request_approval(
        f"NEX Build engine will generate code modifications for issue '{issue}'. Proceed?",
        operation_name="fix_issue",
        risk_level=RiskLevel.HIGH,
        yes_flag=cli_ctx.yes,
    )

    fix_result = {
        "issue": issue,
        "mode": "apply",
        "risk_level": RiskLevel.HIGH.value,
        "approved": True,
        "engine_status": "ready_for_agent_runtime",
        "message": (
            "Developer approval granted. Autonomous code modification engine is scheduled "
            "for subsequent agent-runtime execution phase. No local files were modified."
        ),
    }

    if cli_ctx.json_mode:
        print_json_success("fix", fix_result, cli_ctx.correlation_id)
        return

    cli_ctx.output.print_banner("Issue Fix Execution", f"Issue: {issue}")
    cli_ctx.output.print_success("Developer approval confirmed.")
    cli_ctx.output.print_info(
        "Autonomous code modification engine (LangGraph Build Agent) is scheduled "
        "for subsequent agent-runtime execution phase. Codebase remains untouched."
    )
