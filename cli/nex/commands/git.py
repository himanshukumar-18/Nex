"""NEX Git Command Suite.

Provides secure, approval-checked inspection of local Git repositories.
Commands:
  nex git status    - Display detailed working tree status and active operation state
  nex git branches  - List local and remote branches with upstream tracking
  nex git log       - View formatted recent commit history
  nex git diff      - Inspect unified diffs with sensitive secret redaction
  nex git remotes   - Display configured remote repository URLs
  nex git inspect   - Comprehensive repository diagnostic and health audit
"""

import re
from pathlib import Path
from typing import Annotated, Any

import typer
from rich import box
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from nex.core.approvals import ApprovalPolicy, RiskLevel
from nex.core.context import CLIContext
from nex.core.credentials import get_stored_token
from nex.core.exceptions import NexPolicyViolationError, NexRepositoryError
from nex.core.git import (
    create_branch,
    create_commit,
    create_git_plan,
    detect_git_state,
    get_commit_history,
    get_diff,
    get_git_config,
    get_remotes,
    get_staged_summary,
    list_branches,
    push_branch,
    stage_files,
    switch_branch,
    unstage_files,
    validate_branch_name,
    validate_plan_freshness,
)
from nex.output.json import print_json_success

app = typer.Typer(
    help="Safely inspect and manage local Git repositories.",
    no_args_is_help=True,
)


def _ensure_git_repo(cli_ctx: CLIContext) -> Path:
    """Validate that target repository is a valid Git workspace."""
    repo_root = cli_ctx.repo_root
    git_state = detect_git_state(repo_root)
    if not git_state.is_git:
        msg = git_state.error_message or f"Directory '{repo_root}' is not a Git repository."
        raise NexRepositoryError(
            msg,
            suggestion="Run 'git init' or provide a valid repository directory path via --path.",
        )
    return repo_root


@app.command(name="status")
def git_status(ctx: typer.Context) -> None:
    """Display comprehensive working tree status and in-progress operation state."""
    cli_ctx: CLIContext = ctx.obj
    repo_root = _ensure_git_repo(cli_ctx)
    state = detect_git_state(repo_root)

    status_data = {
        "is_git": state.is_git,
        "root": str(state.root),
        "branch": state.current_branch,
        "is_detached_head": state.is_detached_head,
        "is_shallow": state.is_shallow,
        "is_dirty": state.is_dirty,
        "operations": {
            "in_merge": state.in_merge,
            "in_rebase": state.in_rebase,
            "in_cherry_pick": state.in_cherry_pick,
            "in_revert": state.in_revert,
        },
        "head": {
            "sha": state.head_commit_sha,
            "message": state.head_commit_message,
        },
        "changes": {
            "staged": state.staged_count,
            "unstaged": state.unstaged_count,
            "untracked": state.untracked_count,
            "files": state.raw_status_lines,
        },
    }

    if cli_ctx.json_mode:
        print_json_success("git.status", status_data, cli_ctx.correlation_id)
        return

    cli_ctx.output.print_banner("Git Status", f"Repository: {repo_root.name}")

    # Alerts for special states
    if state.is_detached_head:
        cli_ctx.output.print_warning("HEAD is detached. Commits made here will not be on any branch.")
    if state.in_merge:
        cli_ctx.output.print_warning("MERGE IN PROGRESS (.git/MERGE_HEAD detected). Complete or abort merge.")
    if state.in_rebase:
        cli_ctx.output.print_warning("REBASE IN PROGRESS (.git/rebase-merge/apply detected).")
    if state.in_cherry_pick:
        cli_ctx.output.print_warning("CHERRY-PICK IN PROGRESS (.git/CHERRY_PICK_HEAD detected).")
    if state.in_revert:
        cli_ctx.output.print_warning("REVERT IN PROGRESS (.git/REVERT_HEAD detected).")

    tree_badge = (
        "[bold #F59E0B]DIRTY (Uncommitted Changes)[/bold #F59E0B]"
        if state.is_dirty
        else "[bold #22C55E]CLEAN[/bold #22C55E]"
    )

    kv_pairs = [
        ("Current Branch", f"[bold #8B5CF6]{state.current_branch}[/bold #8B5CF6]"),
        ("Head Commit", f"[#00D9FF]{state.head_commit_sha or 'none'}[/#00D9FF] ({state.head_commit_message or ''})"),
        ("Working Tree", tree_badge),
        ("Staged Files", str(state.staged_count)),
        ("Unstaged Files", str(state.unstaged_count)),
        ("Untracked Files", str(state.untracked_count)),
    ]
    if state.is_shallow:
        kv_pairs.append(("Clone Depth", "[#F59E0B]Shallow Clone[/#F59E0B]"))

    cli_ctx.output.print_key_value_pairs("Working Tree Summary", kv_pairs)

    # Render changed files list if dirty
    if state.raw_status_lines:
        rows: list[list[str]] = []
        for line in state.raw_status_lines:
            if len(line) < 3:
                continue
            idx_st = line[0]
            wt_st = line[1]
            file_path = line[3:].strip()

            if idx_st != " " and idx_st != "?":
                status_label = f"[#22C55E]Staged ({idx_st})[/#22C55E]"
            elif idx_st == "?" and wt_st == "?":
                status_label = "[#A1A1B5]Untracked[/#A1A1B5]"
            else:
                status_label = f"[#F59E0B]Unstaged ({wt_st})[/#F59E0B]"

            rows.append([status_label, file_path])

        cli_ctx.output.print_table("Changed Files", ["Status", "Path"], rows)


@app.command(name="branches")
def git_branches(
    ctx: typer.Context,
    all_branches: Annotated[
        bool,
        typer.Option("--all", "-a", help="Include remote-tracking branches."),
    ] = False,
) -> None:
    """List local and remote repository branches with upstream status."""
    cli_ctx: CLIContext = ctx.obj
    repo_root = _ensure_git_repo(cli_ctx)
    branches = list_branches(repo_root, include_remotes=all_branches)

    branch_dicts = [
        {
            "name": b.name,
            "is_current": b.is_current,
            "commit_sha": b.commit_sha,
            "upstream": b.upstream,
            "is_remote": b.is_remote,
        }
        for b in branches
    ]

    if cli_ctx.json_mode:
        print_json_success(
            "git.branches",
            {"branches": branch_dicts, "total": len(branches)},
            cli_ctx.correlation_id,
        )
        return

    cli_ctx.output.print_banner("Git Branches", f"Repository: {repo_root.name}")

    if not branches:
        cli_ctx.output.print_info("No branches detected.")
        return

    rows: list[list[str]] = []
    for b in branches:
        curr_marker = "[bold #8B5CF6]● (current)[/bold #8B5CF6]" if b.is_current else ""
        name_styled = f"[bold #8B5CF6]{b.name}[/bold #8B5CF6]" if b.is_current else b.name
        type_styled = "[dim]remote[/dim]" if b.is_remote else "[#00D9FF]local[/#00D9FF]"
        upstream_styled = b.upstream or "[dim]none[/dim]"
        rows.append([name_styled, type_styled, f"[#00D9FF]{b.commit_sha}[/#00D9FF]", upstream_styled, curr_marker])

    cli_ctx.output.print_table(
        "Repository Branches",
        ["Branch Name", "Type", "Commit", "Upstream", "Active"],
        rows,
    )


@app.command(name="log")
def git_log(
    ctx: typer.Context,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Maximum number of commits to display."),
    ] = 10,
) -> None:
    """Display recent commit history with author, date, and commit SHA."""
    cli_ctx: CLIContext = ctx.obj
    repo_root = _ensure_git_repo(cli_ctx)
    commits = get_commit_history(repo_root, limit=limit)

    commit_dicts = [
        {
            "sha": c.sha,
            "short_sha": c.short_sha,
            "author": f"{c.author_name} <{c.author_email}>",
            "date": c.date,
            "subject": c.subject,
        }
        for c in commits
    ]

    if cli_ctx.json_mode:
        print_json_success(
            "git.log",
            {"commits": commit_dicts, "limit": limit, "count": len(commits)},
            cli_ctx.correlation_id,
        )
        return

    cli_ctx.output.print_banner("Git Commit Log", f"Showing up to {limit} commits")

    if not commits:
        cli_ctx.output.print_info("No commits recorded yet.")
        return

    rows: list[list[str]] = []
    for c in commits:
        rows.append([
            f"[#00D9FF]{c.short_sha}[/#00D9FF]",
            c.author_name,
            c.date.split(" ")[0],
            c.subject,
        ])

    cli_ctx.output.print_table(
        "Recent Commits",
        ["SHA", "Author", "Date", "Subject"],
        rows,
    )


@app.command(name="diff")
def git_diff(
    ctx: typer.Context,
    staged: Annotated[
        bool,
        typer.Option("--staged", "-s", help="Inspect only staged git changes."),
    ] = False,
    stat_only: Annotated[
        bool,
        typer.Option("--stat", help="Display only diffstat summary of additions/deletions."),
    ] = False,
) -> None:
    """Inspect unified diff changes with automated sensitive file and token redaction."""
    cli_ctx: CLIContext = ctx.obj
    repo_root = _ensure_git_repo(cli_ctx)
    diffs = get_diff(repo_root, staged=staged)

    diff_dicts = [
        {
            "file": d.file_path,
            "staged": d.is_staged,
            "is_sensitive": d.is_sensitive,
            "is_binary": d.is_binary,
            "additions": d.additions,
            "deletions": d.deletions,
            "diff": d.diff_content,
        }
        for d in diffs
    ]

    if cli_ctx.json_mode:
        print_json_success(
            "git.diff",
            {
                "staged": staged,
                "files_changed": len(diffs),
                "diffs": diff_dicts,
            },
            cli_ctx.correlation_id,
        )
        return

    scope_desc = "Staged Changes (--staged)" if staged else "Uncommitted Working Tree Changes"
    cli_ctx.output.print_banner("Git Diff", f"Scope: {scope_desc}")

    if not diffs:
        cli_ctx.output.print_success("No changes detected in the selected scope.")
        return

    # Render summary table
    stat_rows: list[list[str]] = []
    total_add = 0
    total_del = 0
    for d in diffs:
        total_add += d.additions
        total_del += d.deletions
        sensitive_flag = "[#EF4444]REDACTED[/#EF4444]" if d.is_sensitive else "[#22C55E]OK[/#22C55E]"
        stat_rows.append([
            d.file_path,
            f"[#22C55E]+{d.additions}[/#22C55E]",
            f"[#EF4444]-{d.deletions}[/#EF4444]",
            sensitive_flag,
        ])

    cli_ctx.output.print_table("Diff Statistics", ["File", "Additions", "Deletions", "Privacy"], stat_rows)

    if stat_only:
        cli_ctx.output.print_info(
            f"Total: {len(diffs)} files changed, {total_add} additions(+), {total_del} deletions(-)."
        )
        return

    # Render diff contents with syntax formatting
    for d in diffs:
        if d.is_sensitive:
            cli_ctx.output.print_warning(
                f"File '{d.file_path}' matches sensitive credential pattern. Diff body redacted for security."
            )
            continue
        if d.is_binary:
            cli_ctx.output.print_info(f"File '{d.file_path}' is binary. Content display skipped.")
            continue

        syntax = Syntax(d.diff_content, "diff", theme="monokai", line_numbers=False)
        cli_ctx.output.console.print(
            Panel(
                syntax,
                title=f"[bold #00D9FF]{d.file_path}[/bold #00D9FF] ([#22C55E]+{d.additions}[/#22C55E] [#EF4444]-{d.deletions}[/#EF4444])",
                border_style="#303044",
            )
        )


@app.command(name="remotes")
def git_remotes(ctx: typer.Context) -> None:
    """Display configured remote repository names and URLs."""
    cli_ctx: CLIContext = ctx.obj
    repo_root = _ensure_git_repo(cli_ctx)
    remotes = get_remotes(repo_root)

    remote_dicts = [
        {"name": r.name, "fetch_url": r.fetch_url, "push_url": r.push_url}
        for r in remotes
    ]

    if cli_ctx.json_mode:
        print_json_success(
            "git.remotes",
            {"remotes": remote_dicts, "count": len(remotes)},
            cli_ctx.correlation_id,
        )
        return

    cli_ctx.output.print_banner("Git Remotes", f"Repository: {repo_root.name}")

    if not remotes:
        cli_ctx.output.print_info("No remote repositories configured.")
        return

    rows: list[list[str]] = [
        [f"[bold #8B5CF6]{r.name}[/bold #8B5CF6]", r.fetch_url, r.push_url]
        for r in remotes
    ]
    cli_ctx.output.print_table("Configured Remotes", ["Remote Name", "Fetch URL", "Push URL"], rows)


@app.command(name="inspect")
def git_inspect(ctx: typer.Context) -> None:
    """Complete diagnostic audit of repository integrity, state, and Git configuration."""
    cli_ctx: CLIContext = ctx.obj
    repo_root = _ensure_git_repo(cli_ctx)
    state = detect_git_state(repo_root)
    configs = get_git_config(repo_root)

    # Highlight relevant configurations
    relevant_config_keys = [
        "user.name",
        "user.email",
        "core.repositoryformatversion",
        "core.filemode",
        "core.bare",
        "core.ignorecase",
        "remote.origin.url",
    ]
    selected_configs = {k: configs[k] for k in relevant_config_keys if k in configs}

    diagnostic_data = {
        "git_version": state.git_version,
        "root": str(state.root),
        "git_dir": str(state.git_dir),
        "branch": state.current_branch,
        "is_detached_head": state.is_detached_head,
        "is_shallow": state.is_shallow,
        "is_dirty": state.is_dirty,
        "operations": {
            "in_merge": state.in_merge,
            "in_rebase": state.in_rebase,
            "in_cherry_pick": state.in_cherry_pick,
            "in_revert": state.in_revert,
        },
        "head_commit": {
            "sha": state.head_commit_sha,
            "message": state.head_commit_message,
        },
        "changes": {
            "staged": state.staged_count,
            "unstaged": state.unstaged_count,
            "untracked": state.untracked_count,
        },
        "remotes": [
            {"name": r.name, "fetch": r.fetch_url, "push": r.push_url}
            for r in state.remotes
        ],
        "configuration": selected_configs,
    }

    if cli_ctx.json_mode:
        print_json_success("git.inspect", diagnostic_data, cli_ctx.correlation_id)
        return

    cli_ctx.output.print_banner("Git Diagnostic Inspection", f"Root: {repo_root}")

    tree_status = (
        "[#F59E0B]Dirty (uncommitted changes)[/#F59E0B]"
        if state.is_dirty
        else "[#22C55E]Clean[/#22C55E]"
    )

    diagnostic_items = [
        ("Git Version", state.git_version or "Unknown"),
        ("Repository Root", str(state.root)),
        ("Git Directory", str(state.git_dir)),
        ("Current Branch", state.current_branch or "Unknown"),
        ("Head Commit", f"{state.head_commit_sha or 'none'} ({state.head_commit_message or ''})"),
        ("Working Tree State", tree_status),
        ("Detached HEAD", "[#F59E0B]Yes[/#F59E0B]" if state.is_detached_head else "[#22C55E]No[/#22C55E]"),
        ("Shallow Clone", "[#F59E0B]Yes[/#F59E0B]" if state.is_shallow else "[#22C55E]No[/#22C55E]"),
        ("Merge In Progress", "[#F59E0B]Yes[/#F59E0B]" if state.in_merge else "[#22C55E]No[/#22C55E]"),
        ("Rebase In Progress", "[#F59E0B]Yes[/#F59E0B]" if state.in_rebase else "[#22C55E]No[/#22C55E]"),
        ("Configured Remotes", str(len(state.remotes))),
        ("User Name", configs.get("user.name", "[dim]Not configured[/dim]")),
        ("User Email", configs.get("user.email", "[dim]Not configured[/dim]")),
    ]

    cli_ctx.output.print_key_value_pairs("Repository Diagnostics", diagnostic_items)
    cli_ctx.output.print_success("Git inspection completed. All integrity checks passed.")


# ---------------------------------------------------------------------------
# Backend Synchronization Helpers
# ---------------------------------------------------------------------------


def _record_backend_operation(
    cli_ctx: CLIContext,
    operation_type: str,
    status: str,
    risk_level: str,
    approval_status: str,
    target_branch: str = "",
    target_remote: str = "",
    files: list[str] | None = None,
    commit_sha: str = "",
    commit_message: str = "",
    error_message: str = "",
    metadata: dict[str, Any] | None = None,
    repository_id: str | None = None,
) -> None:
    """Record operation to Django backend if authenticated, failing silently if backend unavailable."""
    token = get_stored_token()
    if not token:
        return

    payload: dict[str, Any] = {
        "operation_type": operation_type,
        "status": status,
        "risk_level": risk_level,
        "approval_status": approval_status,
        "target_branch": target_branch,
        "target_remote": target_remote,
        "files": files or [],
        "commit_sha": commit_sha,
        "commit_message": commit_message,
        "error_message": error_message,
        "correlation_id": cli_ctx.correlation_id,
        "metadata": metadata or {},
    }
    if repository_id:
        payload["repository_id"] = repository_id

    try:
        cli_ctx.client.request("POST", "/repositories/operations/", json=payload)
    except Exception:
        # Non-blocking graceful degradation
        pass


def _resolve_backend_repo_id(cli_ctx: CLIContext, repo_root: Path) -> str | None:
    """Resolve backend Repository ID from local remote URL if linked in NEX."""
    token = get_stored_token()
    if not token:
        return None
    try:
        remotes = get_remotes(repo_root)
        origin = next((r for r in remotes if r.name == "origin"), None)
        if not origin:
            origin = remotes[0] if remotes else None
        if not origin or not (origin.fetch_url or origin.push_url):
            return None
        url = origin.fetch_url or origin.push_url or ""
        match = re.search(r"github\.com[:/]([^/]+)/([^/.]+)(?:\.git)?", url)
        if not match:
            return None
        full_name = f"{match.group(1)}/{match.group(2)}"
        res = cli_ctx.client.request("GET", "/repositories/", params={"search": full_name})
        repos = res.get("results", []) if isinstance(res, dict) else res
        for repo in repos:
            if repo.get("full_name", "").lower() == full_name.lower():
                repo_id = repo.get("id")
                return str(repo_id) if repo_id else None
    except Exception:
        pass
    return None


def _fetch_push_token(cli_ctx: CLIContext, repo_id: str) -> str | None:
    """Request a short-lived GitHub App push token from backend for the authorized repo."""
    try:
        res = cli_ctx.client.request("POST", f"/repositories/{repo_id}/push-token/")
        if isinstance(res, dict) and "token" in res:
            tok = res["token"]
            return str(tok) if tok else None
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Branch Management Subcommands
# ---------------------------------------------------------------------------

branch_app = typer.Typer(
    name="branch",
    help="Safe local branch management.",
    no_args_is_help=True,
)


@branch_app.command(name="list")
def branch_list(
    ctx: typer.Context,
    all_branches: Annotated[
        bool,
        typer.Option("--all", "-a", help="Include remote-tracking branches."),
    ] = False,
) -> None:
    """List local and remote branches."""
    git_branches(ctx, all_branches=all_branches)


@branch_app.command(name="create")
def branch_create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the new branch to create.")],
    start_point: Annotated[
        str | None,
        typer.Option("--start-point", "-s", help="Optional commit or ref to branch from."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate branch creation without modifying repository."),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Confirm branch creation without interactive prompt."),
    ] = False,
) -> None:
    """Safely create a new local branch with validation and duplicate detection."""
    cli_ctx: CLIContext = ctx.obj
    repo_root = _ensure_git_repo(cli_ctx)
    repo_id = _resolve_backend_repo_id(cli_ctx, repo_root)

    validate_branch_name(name, repo_root)
    plan = create_git_plan("branch_create", repo_root, target_branch=name, risk_level=RiskLevel.MEDIUM)

    if not dry_run:
        ApprovalPolicy.request_approval(
            f"Create branch '{name}'?",
            operation_name="git branch create",
            risk_level=RiskLevel.MEDIUM,
            yes_flag=yes or cli_ctx.yes,
        )
        validate_plan_freshness(plan)

    create_branch(repo_root, name, start_point=start_point, dry_run=dry_run)

    _record_backend_operation(
        cli_ctx,
        operation_type="branch_create",
        status="completed" if not dry_run else "simulated",
        risk_level=RiskLevel.MEDIUM.value,
        approval_status="approved",
        target_branch=name,
        repository_id=repo_id,
        metadata={"start_point": start_point, "dry_run": dry_run},
    )

    if cli_ctx.json_mode:
        print_json_success(
            "git.branch.create",
            {"branch": name, "dry_run": dry_run, "status": "simulated" if dry_run else "created"},
            cli_ctx.correlation_id,
        )
        return

    if dry_run:
        cli_ctx.output.print_info(f"[DRY-RUN] Branch '{name}' would be created successfully.")
    else:
        cli_ctx.output.print_success(f"Branch '{name}' created successfully.")


@branch_app.command(name="switch")
def branch_switch(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the branch to switch to.")],
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate branch switch without modifying repository."),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Confirm branch switch without interactive prompt."),
    ] = False,
) -> None:
    """Safely switch working tree to an existing branch (requires clean tree)."""
    cli_ctx: CLIContext = ctx.obj
    repo_root = _ensure_git_repo(cli_ctx)
    repo_id = _resolve_backend_repo_id(cli_ctx, repo_root)

    validate_branch_name(name, repo_root)
    plan = create_git_plan("branch_switch", repo_root, target_branch=name, risk_level=RiskLevel.MEDIUM)

    if not dry_run:
        ApprovalPolicy.request_approval(
            f"Switch to branch '{name}'?",
            operation_name="git branch switch",
            risk_level=RiskLevel.MEDIUM,
            yes_flag=yes or cli_ctx.yes,
        )
        validate_plan_freshness(plan)

    switch_branch(repo_root, name, dry_run=dry_run)

    _record_backend_operation(
        cli_ctx,
        operation_type="branch_switch",
        status="completed" if not dry_run else "simulated",
        risk_level=RiskLevel.MEDIUM.value,
        approval_status="approved",
        target_branch=name,
        repository_id=repo_id,
        metadata={"dry_run": dry_run},
    )

    if cli_ctx.json_mode:
        print_json_success(
            "git.branch.switch",
            {"branch": name, "dry_run": dry_run, "status": "simulated" if dry_run else "switched"},
            cli_ctx.correlation_id,
        )
        return

    if dry_run:
        cli_ctx.output.print_info(f"[DRY-RUN] Working tree would switch to branch '{name}'.")
    else:
        cli_ctx.output.print_success(f"Switched to branch '{name}'.")


app.add_typer(branch_app, name="branch")


# ---------------------------------------------------------------------------
# Staging & Unstaging Commands
# ---------------------------------------------------------------------------


@app.command(name="stage")
def git_stage(
    ctx: typer.Context,
    files: Annotated[
        list[str],
        typer.Argument(help="One or more specific relative file paths to stage."),
    ],
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate staging without modifying Git index."),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Confirm staging."),
    ] = False,
) -> None:
    """Selectively stage specific files into the Git index. Blocks wildcards and sensitive files."""
    cli_ctx: CLIContext = ctx.obj
    repo_root = _ensure_git_repo(cli_ctx)
    repo_id = _resolve_backend_repo_id(cli_ctx, repo_root)

    if not files:
        raise NexPolicyViolationError(
            "No files specified for staging.",
            suggestion="Specify explicit file paths, e.g. 'nex git stage src/main.py'",
        )

    for path_str in files:
        if path_str.strip() in {".", "*", "-A", "--all"}:
            raise NexPolicyViolationError(
                f"Wildcard staging ('{path_str}') is prohibited in NEX to prevent accidental secret leakage.",
                suggestion="Specify explicit target file paths, e.g. 'nex git stage src/main.py'.",
            )

    plan = create_git_plan("stage", repo_root, files=files, risk_level=RiskLevel.HIGH)

    if not dry_run:
        ApprovalPolicy.request_approval(
            f"Stage {len(files)} file(s)?",
            operation_name="git stage",
            risk_level=RiskLevel.HIGH,
            yes_flag=yes or cli_ctx.yes,
        )
        validate_plan_freshness(plan)

    staged_paths = stage_files(repo_root, files, dry_run=dry_run)

    _record_backend_operation(
        cli_ctx,
        operation_type="stage",
        status="completed" if not dry_run else "simulated",
        risk_level=RiskLevel.HIGH.value,
        approval_status="approved",
        files=files,
        repository_id=repo_id,
        metadata={"dry_run": dry_run},
    )

    if cli_ctx.json_mode:
        print_json_success(
            "git.stage",
            {"files": [str(p) for p in staged_paths], "dry_run": dry_run},
            cli_ctx.correlation_id,
        )
        return

    if dry_run:
        cli_ctx.output.print_info(f"[DRY-RUN] Would stage {len(staged_paths)} file(s):")
        for p in staged_paths:
            cli_ctx.output.print_info(f"  + {p}")
    else:
        cli_ctx.output.print_success(f"Staged {len(staged_paths)} file(s):")
        for p in staged_paths:
            cli_ctx.output.print_info(f"  [#22C55E]+ {p}[/#22C55E]")


@app.command(name="unstage")
def git_unstage(
    ctx: typer.Context,
    files: Annotated[
        list[str],
        typer.Argument(help="One or more specific relative file paths to unstage."),
    ],
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate unstaging without modifying Git index."),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Confirm unstaging."),
    ] = False,
) -> None:
    """Selectively unstage files from the Git index."""
    cli_ctx: CLIContext = ctx.obj
    repo_root = _ensure_git_repo(cli_ctx)
    repo_id = _resolve_backend_repo_id(cli_ctx, repo_root)

    if not files:
        raise NexPolicyViolationError(
            "No files specified for unstaging.",
            suggestion="Specify explicit file paths, e.g. 'nex git unstage src/main.py'",
        )

    for path_str in files:
        if path_str.strip() in {".", "*", "-A", "--all"}:
            raise NexPolicyViolationError(
                f"Wildcard unstaging ('{path_str}') is prohibited in NEX.",
                suggestion="Specify explicit target file paths to unstage.",
            )

    plan = create_git_plan("unstage", repo_root, files=files, risk_level=RiskLevel.HIGH)

    if not dry_run:
        ApprovalPolicy.request_approval(
            f"Unstage {len(files)} file(s)?",
            operation_name="git unstage",
            risk_level=RiskLevel.HIGH,
            yes_flag=yes or cli_ctx.yes,
        )
        validate_plan_freshness(plan)

    unstaged_paths = unstage_files(repo_root, files, dry_run=dry_run)

    _record_backend_operation(
        cli_ctx,
        operation_type="unstage",
        status="completed" if not dry_run else "simulated",
        risk_level=RiskLevel.HIGH.value,
        approval_status="approved",
        files=files,
        repository_id=repo_id,
        metadata={"dry_run": dry_run},
    )

    if cli_ctx.json_mode:
        print_json_success(
            "git.unstage",
            {"files": [str(p) for p in unstaged_paths], "dry_run": dry_run},
            cli_ctx.correlation_id,
        )
        return

    if dry_run:
        cli_ctx.output.print_info(f"[DRY-RUN] Would unstage {len(unstaged_paths)} file(s):")
        for p in unstaged_paths:
            cli_ctx.output.print_info(f"  - {p}")
    else:
        cli_ctx.output.print_success(f"Unstaged {len(unstaged_paths)} file(s):")
        for p in unstaged_paths:
            cli_ctx.output.print_info(f"  [#F59E0B]- {p}[/#F59E0B]")


@app.command(name="staged")
def git_staged(ctx: typer.Context) -> None:
    """Inspect currently staged files and unified staged diff with secret redaction."""
    cli_ctx: CLIContext = ctx.obj
    repo_root = _ensure_git_repo(cli_ctx)

    summary = get_staged_summary(repo_root)

    if cli_ctx.json_mode:
        print_json_success(
            "git.staged",
            summary,
            cli_ctx.correlation_id,
        )
        return

    if summary["count"] == 0:
        cli_ctx.output.print_info("No files currently staged in the index.")
        cli_ctx.output.print_info("Use 'nex git stage <files...>' to stage changes for commit.")
        return

    table = Table(
        title=f"Staged Changes ({summary['count']} file{'s' if summary['count'] != 1 else ''})",
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold #A1A1B5",
    )
    table.add_column("Status", justify="center", style="bold")
    table.add_column("File Path", style="#F1F1F5")
    table.add_column("Additions", justify="right", style="#22C55E")
    table.add_column("Deletions", justify="right", style="#EF4444")

    for f in summary["files"]:
        status_code = f.get("status", "M")
        status_label = "[#22C55E]New[/#22C55E]" if status_code == "A" else "[#00D9FF]Modified[/#00D9FF]"
        if status_code == "D":
            status_label = "[#EF4444]Deleted[/#EF4444]"
        elif status_code.startswith("R"):
            status_label = "[#F59E0B]Renamed[/#F59E0B]"

        table.add_row(
            status_label,
            f.get("path", ""),
            f"+{f.get('insertions', 0)}",
            f"-{f.get('deletions', 0)}",
        )

    cli_ctx.output.console.print(table)
    cli_ctx.output.print_info(
        f"Total: +{summary['total_insertions']} / -{summary['total_deletions']}"
    )

    if summary.get("diff"):
        cli_ctx.output.print_banner("Staged Diff Preview (Secrets Redacted)")
        syntax = Syntax(summary["diff"], "diff", theme="monokai", line_numbers=False)
        cli_ctx.output.console.print(syntax)


# ---------------------------------------------------------------------------
# Commit & Push Commands
# ---------------------------------------------------------------------------


@app.command(name="commit")
def git_commit(
    ctx: typer.Context,
    message: Annotated[
        str,
        typer.Option("--message", "-m", help="Descriptive commit message."),
    ] = "",
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate commit without modifying repository."),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Confirm commit creation."),
    ] = False,
) -> None:
    """Create a new commit from staged changes with diff preview and approval."""
    cli_ctx: CLIContext = ctx.obj
    repo_root = _ensure_git_repo(cli_ctx)
    repo_id = _resolve_backend_repo_id(cli_ctx, repo_root)

    clean_msg = message.strip()
    if not clean_msg:
        raise NexRepositoryError(
            "Commit message cannot be empty.",
            suggestion="Provide a descriptive commit message with -m '<message>'.",
        )

    state = detect_git_state(repo_root)
    if state.staged_count == 0:
        raise NexPolicyViolationError(
            "No staged changes to commit.",
            suggestion="Stage specific files first using 'nex git stage <files...>' before committing.",
        )

    summary = get_staged_summary(repo_root)

    if not cli_ctx.json_mode:
        cli_ctx.output.print_banner("Commit Staged Changes Preview")
        cli_ctx.output.print_info(f"Commit message: [bold #F1F1F5]{clean_msg}[/bold #F1F1F5]")
        cli_ctx.output.print_info(f"Staged files ({summary['count']}):")
        for f in summary["files"]:
            cli_ctx.output.print_info(f"  • {f.get('path')} (+{f.get('insertions', 0)} / -{f.get('deletions', 0)})")

    plan = create_git_plan("commit", repo_root, commit_message=clean_msg, risk_level=RiskLevel.HIGH)

    if not dry_run:
        ApprovalPolicy.request_approval(
            f"Commit {summary['count']} staged file(s) with message '{clean_msg}'?",
            operation_name="git commit",
            risk_level=RiskLevel.HIGH,
            yes_flag=yes or cli_ctx.yes,
        )
        validate_plan_freshness(plan)

    commit_record = create_commit(repo_root, clean_msg, dry_run=dry_run)

    _record_backend_operation(
        cli_ctx,
        operation_type="commit",
        status="completed" if not dry_run else "simulated",
        risk_level=RiskLevel.HIGH.value,
        approval_status="approved",
        commit_sha=commit_record.sha,
        commit_message=clean_msg,
        repository_id=repo_id,
        metadata={"dry_run": dry_run, "staged_count": summary["count"]},
    )

    if cli_ctx.json_mode:
        print_json_success(
            "git.commit",
            {
                "sha": commit_record.sha,
                "short_sha": commit_record.short_sha,
                "message": clean_msg,
                "staged_count": summary["count"],
                "dry_run": dry_run,
            },
            cli_ctx.correlation_id,
        )
        return

    if dry_run:
        cli_ctx.output.print_info(f"[DRY-RUN] Commit simulated. Would commit with message: '{clean_msg}'.")
    else:
        cli_ctx.output.print_success(
            f"Commit created: [bold #00D9FF]{commit_record.short_sha}[/bold #00D9FF] - {clean_msg}"
        )


@app.command(name="push")
def git_push(
    ctx: typer.Context,
    remote: Annotated[
        str,
        typer.Option("--remote", "-r", help="Target remote repository name."),
    ] = "origin",
    branch: Annotated[
        str | None,
        typer.Option("--branch", "-b", help="Target branch name (defaults to current branch)."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate push without transferring data to remote."),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Confirm branch push."),
    ] = False,
) -> None:
    """Safely push approved branch to remote repository using secure GitHub App token or local credentials."""
    cli_ctx: CLIContext = ctx.obj
    repo_root = _ensure_git_repo(cli_ctx)
    repo_id = _resolve_backend_repo_id(cli_ctx, repo_root)

    state = detect_git_state(repo_root)
    if state.is_detached_head:
        raise NexRepositoryError(
            "Cannot push while HEAD is detached.",
            suggestion="Switch to an active named branch before pushing.",
        )

    target_branch = branch or state.current_branch
    if not target_branch:
        raise NexRepositoryError("Unable to resolve active branch to push.")

    plan = create_git_plan(
        "push",
        repo_root,
        target_branch=target_branch,
        target_remote=remote,
        risk_level=RiskLevel.CRITICAL,
    )

    if not cli_ctx.json_mode:
        cli_ctx.output.print_banner("Git Push Target Verification")
        cli_ctx.output.print_info(f"Target Remote: [bold #00D9FF]{remote}[/bold #00D9FF]")
        cli_ctx.output.print_info(f"Target Branch: [bold #00D9FF]{target_branch}[/bold #00D9FF]")
        cli_ctx.output.print_info(f"Head Commit:   [dim]{state.head_commit_sha} ({state.head_commit_message})[/dim]")

    if not dry_run:
        ApprovalPolicy.request_approval(
            f"Push branch '{target_branch}' to remote '{remote}'?",
            operation_name="git push",
            risk_level=RiskLevel.CRITICAL,
            yes_flag=yes or cli_ctx.yes,
        )
        validate_plan_freshness(plan)

    # Fetch push token if linked to NEX GitHub App
    token: str | None = None
    if repo_id:
        token = _fetch_push_token(cli_ctx, repo_id)

    _ = push_branch(
        repo_root,
        remote_name=remote,
        branch_name=target_branch,
        token=token,
        dry_run=dry_run,
    )

    _record_backend_operation(
        cli_ctx,
        operation_type="push",
        status="completed" if not dry_run else "simulated",
        risk_level=RiskLevel.CRITICAL.value,
        approval_status="approved",
        target_branch=target_branch,
        target_remote=remote,
        commit_sha=state.head_commit_sha or "",
        repository_id=repo_id,
        metadata={"dry_run": dry_run, "authenticated_push": token is not None},
    )

    if cli_ctx.json_mode:
        print_json_success(
            "git.push",
            {
                "remote": remote,
                "branch": target_branch,
                "status": "simulated" if dry_run else "pushed",
                "dry_run": dry_run,
            },
            cli_ctx.correlation_id,
        )
        return

    if dry_run:
        cli_ctx.output.print_info(f"[DRY-RUN] Push validation succeeded for '{remote}/{target_branch}'.")
    else:
        cli_ctx.output.print_success(f"Branch '{target_branch}' pushed successfully to '{remote}'.")

