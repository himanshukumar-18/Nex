"""NEX Test Command.

Verifies code correctness across the hybrid execution architecture (Local vs Isolated Sandbox).
Enforces execution safety policies preventing untrusted code from running directly on developer machines.
"""

from typing import Annotated

import typer

from nex.core.approvals import ApprovalPolicy, RiskLevel
from nex.core.context import CLIContext
from nex.core.execution_policy import ExecutionTarget
from nex.output.json import print_json_success

app = typer.Typer(help="Run automated tests using hybrid execution policy.")


@app.callback(invoke_without_command=True)
def test(
    ctx: typer.Context,
    local: Annotated[
        bool,
        typer.Option(
            "--local",
            "-l",
            help="Force local test execution (bypasses sandbox isolation).",
        ),
    ] = False,
    test_target: Annotated[
        str | None,
        typer.Option(
            "--target", "-t", help="Specific test path or pattern to execute."
        ),
    ] = None,
) -> None:
    """Execute test suites respecting hybrid sandbox isolation policies."""
    cli_ctx: CLIContext = ctx.obj

    target_env = ExecutionTarget.LOCAL if local else ExecutionTarget.REMOTE_SANDBOX

    if local:
        # Local execution of test suites requires HIGH risk approval
        ApprovalPolicy.request_approval(
            "Executing tests locally bypasses isolated sandbox containerization. Proceed?",
            operation_name="local_test_execution",
            risk_level=RiskLevel.HIGH,
            yes_flag=cli_ctx.yes,
        )

        test_data = {
            "execution_target": target_env.value,
            "target": test_target or "all",
            "policy": "local_direct",
            "status": "policy_approved",
            "message": (
                "Local test execution policy approved. Direct test runner integration "
                "is scheduled for subsequent verification engine phase."
            ),
        }
    else:
        # Remote sandbox is the secure default
        test_data = {
            "execution_target": target_env.value,
            "target": test_target or "all",
            "policy": "isolated_sandbox",
            "status": "ready_for_agent_runtime",
            "message": (
                "Hybrid execution policy: Test verification routed to isolated container sandbox. "
                "Sandbox runner is scheduled for subsequent agent-runtime phase."
            ),
        }

    if cli_ctx.json_mode:
        print_json_success("test", test_data, cli_ctx.correlation_id)
        return

    cli_ctx.output.print_banner(
        "Verification & Test Execution", f"Target: {test_target or 'default suite'}"
    )

    env_label = (
        "[bold #F59E0B]LOCAL (UNSANDBOXED)[/bold #F59E0B]"
        if local
        else "[bold #22C55E]ISOLATED SANDBOX (DEFAULT)[/bold #22C55E]"
    )
    cli_ctx.output.print_key_value_pairs(
        "Execution Policy",
        [
            ("Target Environment", env_label),
            ("Selected Target", test_target or "all"),
            ("Sandbox Isolation", "Disabled" if local else "Enforced"),
            ("Safety Status", "Policy Compliant"),
        ],
    )

    if local:
        cli_ctx.output.print_warning(
            "Local test execution was confirmed. In production, untrusted test suites "
            "should execute in isolated sandboxes to prevent host environment tampering."
        )
    else:
        cli_ctx.output.print_info(
            "Isolated sandbox test runner is scheduled for subsequent agent-runtime execution phase. "
            "Developer host environment remains secure."
        )
