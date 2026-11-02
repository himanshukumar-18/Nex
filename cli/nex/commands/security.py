"""NEX Security Command.

Scans the local repository workspace for exposed credentials, sensitive files,
private keys, and insecure file permissions.
"""

from typing import Annotated

import typer

from nex.core.context import CLIContext
from nex.core.exceptions import NexPolicyViolationError
from nex.core.repository import scan_sensitive_files
from nex.output.json import print_json_success

app = typer.Typer(help="Scan repository for sensitive files and exposed secrets.")


@app.callback(invoke_without_command=True)
def security(
    ctx: typer.Context,
    strict: Annotated[
        bool,
        typer.Option(
            "--strict",
            "-s",
            help="Enforce failure exit code if any sensitive files are found.",
        ),
    ] = False,
) -> None:
    """Scan local repository workspace for credentials, private keys, and loose permissions."""
    cli_ctx: CLIContext = ctx.obj
    repo_root = cli_ctx.repo_root

    findings = scan_sensitive_files(repo_root)
    has_violations = len(findings) > 0

    result_data = {
        "repository": str(repo_root),
        "total_violations": len(findings),
        "strict_mode": strict,
        "findings": findings,
        "clean": not has_violations,
    }

    if cli_ctx.json_mode:
        print_json_success("security", result_data, cli_ctx.correlation_id)
        if strict and has_violations:
            raise NexPolicyViolationError(
                f"Security scan failed: {len(findings)} sensitive files detected under --strict mode.",
                suggestion="Add sensitive files to .gitignore or remove them before committing.",
            )
        return

    cli_ctx.output.print_banner(
        "Security & Credential Audit", f"Workspace: {repo_root.name}"
    )

    if not has_violations:
        cli_ctx.output.print_success(
            "Security scan passed. No exposed secrets or private keys detected."
        )
        cli_ctx.output.print_info(
            "Sensitive patterns checked: .env*, *.pem, *.key, id_rsa*, credentials.json"
        )
        return

    # Render findings table
    table_rows = []
    for item in findings:
        perm_warning = (
            "[bold #EF4444]WORLD-READABLE[/bold #EF4444]"
            if item["world_readable"]
            else item["mode"]
        )
        table_rows.append([item["path"], item["matched_pattern"], perm_warning])

    cli_ctx.output.print_table(
        "Detected Sensitive Files",
        ["Path", "Pattern", "Permissions"],
        table_rows,
    )

    cli_ctx.output.print_warning(
        f"Found {len(findings)} sensitive files that should not be committed or transmitted to remote agents."
    )
    cli_ctx.output.print_info(
        "Recommendation: Ensure all detected paths are listed in .gitignore."
    )

    if strict:
        raise NexPolicyViolationError(
            f"Security scan failed: {len(findings)} sensitive files detected under --strict mode.",
            suggestion="Add sensitive files to .gitignore or remove them before committing.",
        )
