"""NEX Pull Request (PR) Command Suite.

Prepares, previews, and publishes developer-approved pull requests to GitHub.
Enforces strict CRITICAL-risk human approval boundaries (cannot be bypassed with --yes).
Includes verification against unpushed local commits (anti-silent-push policy).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Any

import typer
from rich import box
from rich.panel import Panel
from rich.table import Table

from nex.client.exceptions import NexClientAuthError, NexClientError
from nex.core.approvals import ApprovalPolicy, RiskLevel
from nex.core.context import CLIContext
from nex.core.credentials import clear_credentials, get_stored_token
from nex.core.exceptions import (
    NexError,
    NexPolicyViolationError,
    NexRepositoryError,
)
from nex.core.exit_codes import ExitCode
from nex.core.git import detect_git_state, get_remotes, run_git
from nex.output.json import print_json_success
from nex.output.terminal import console

app = typer.Typer(
    name="pr",
    help="Create, inspect, and manage GitHub pull requests.",
    no_args_is_help=False,
)

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


def _require_auth() -> str:
    """Ensure user is authenticated before interacting with NEX backend."""
    token = get_stored_token()
    if not token:
        raise NexError(
            "Not authenticated. Please run 'nex login' first.",
            exit_code=ExitCode.AUTH_ERROR,
            suggestion="Run 'nex login' to sign in via your web browser.",
        )
    return token


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


def _resolve_repo(
    cli_ctx: CLIContext, repo_identifier: str | None, repo_root: Path | None
) -> dict[str, Any]:
    """Resolve repository data dictionary from explicit identifier or local git remote."""
    _require_auth()
    resolved_id: str | None = None

    if repo_identifier:
        ident = repo_identifier.strip()
        if UUID_PATTERN.match(ident):
            resolved_id = ident
        else:
            try:
                res = cli_ctx.client.request(
                    "GET", "/repositories/", params={"search": ident, "page_size": 10}
                )
                candidates = res.get("results", []) if isinstance(res, dict) else res
                for cand in candidates:
                    if (
                        cand.get("full_name", "").lower() == ident.lower()
                        or cand.get("name", "").lower() == ident.lower()
                        or str(cand.get("github_repo_id")) == ident
                    ):
                        resolved_id = cand.get("id")
                        break
                if not resolved_id and candidates:
                    resolved_id = candidates[0].get("id")
            except NexClientError as exc:
                raise NexError(
                    f"Failed to lookup repository '{ident}': {exc.message}",
                    exit_code=ExitCode.BACKEND_UNAVAILABLE,
                ) from exc
    elif repo_root:
        resolved_id = _resolve_backend_repo_id(cli_ctx, repo_root)

    if not resolved_id:
        raise NexRepositoryError(
            "Current repository is not linked to any synchronized GitHub repository in NEX.",
            suggestion="Run 'nex repos sync' or specify the target repository with --repo <name>.",
        )

    try:
        repo_data = cli_ctx.client.request("GET", f"/repositories/{resolved_id}/")
        return repo_data  # type: ignore[no-any-return]
    except NexClientAuthError as exc:
        clear_credentials()
        raise NexError(
            "Authentication token has expired or been revoked.",
            exit_code=ExitCode.AUTH_ERROR,
            suggestion="Run 'nex login' to log in again.",
        ) from exc
    except NexClientError as exc:
        raise NexError(
            f"Failed to fetch repository metadata: {exc.message}",
            exit_code=ExitCode.BACKEND_UNAVAILABLE,
        ) from exc


def _verify_head_branch_pushed(repo_root: Path, head_branch: str, remote_name: str = "origin") -> None:
    """Verify that head branch exists on remote and local commits are fully pushed.

    Enforces the NEX anti-silent-push policy: pull requests can only be opened for
    branches that the developer has already explicitly pushed to GitHub.
    """
    # 1. Check if remote tracking branch exists locally
    chk_ref = run_git(["rev-parse", "--verify", "--quiet", f"refs/remotes/{remote_name}/{head_branch}"], repo_root)
    if chk_ref.returncode != 0:
        raise NexRepositoryError(
            f"Branch '{head_branch}' does not exist on remote '{remote_name}'.",
            suggestion=f"Push your branch first using 'nex git push --branch {head_branch}' before opening a pull request.",
        )

    # 2. Check if local commits are ahead of remote
    chk_ahead = run_git(["rev-list", "--count", f"refs/remotes/{remote_name}/{head_branch}..HEAD"], repo_root)
    if chk_ahead.returncode == 0:
        unpushed_count = int(chk_ahead.stdout.strip() or 0)
        if unpushed_count > 0:
            raise NexRepositoryError(
                f"Branch '{head_branch}' has {unpushed_count} unpushed commit(s) on local.",
                suggestion=f"Push your changes first using 'nex git push --branch {head_branch}' before creating a pull request.",
            )


@app.callback(invoke_without_command=True)
def pr_root(
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
    base: Annotated[
        str | None,
        typer.Option("--base", "-B", help="Base branch to merge into (defaults to repo default branch)."),
    ] = None,
    target: Annotated[
        str | None,
        typer.Option("--target", hidden=True, help="Alias for --base."),
    ] = None,
    head: Annotated[
        str | None,
        typer.Option("--head", "-H", help="Head branch containing changes (defaults to current branch)."),
    ] = None,
    repo: Annotated[
        str | None,
        typer.Option("--repo", "-R", help="Target repository UUID or owner/name slug."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview PR comparison and payload without publishing."),
    ] = False,
) -> None:
    """Prepare, preview, and publish a pull request to GitHub."""
    if ctx.invoked_subcommand is not None:
        return

    cli_ctx: CLIContext = ctx.obj
    ApprovalPolicy.check_yes_flag_eligibility(
        "create_pull_request", RiskLevel.CRITICAL, cli_ctx.yes
    )
    _require_auth()
    repo_root = _ensure_git_repo(cli_ctx)
    state = detect_git_state(repo_root)

    if state.is_detached_head:
        raise NexRepositoryError(
            "Cannot create a pull request while HEAD is detached.",
            suggestion="Switch to a named branch using 'nex git branch switch <name>' before creating a pull request.",
        )

    head_branch = head or state.current_branch
    if not head_branch:
        raise NexRepositoryError(
            "Unable to resolve active head branch for pull request.",
            suggestion="Specify the head branch explicitly via --head <name>.",
        )

    repo_data = _resolve_repo(cli_ctx, repo, repo_root)
    repo_id = str(repo_data["id"])
    repo_full_name = repo_data.get("full_name", "unknown")

    base_branch = base or target or repo_data.get("default_branch") or "main"

    if head_branch == base_branch:
        raise NexPolicyViolationError(
            f"Head branch '{head_branch}' cannot be the same as base branch '{base_branch}'.",
            suggestion="Specify a different base branch with --base or switch to a feature branch.",
        )

    # Enforce anti-silent-push verification
    _verify_head_branch_pushed(repo_root, head_branch)

    # 1. Preview changes against base branch
    try:
        preview = cli_ctx.client.request(
            "POST",
            f"/repositories/{repo_id}/pulls/preview/",
            json={"head": head_branch, "base": base_branch},
        )
    except NexClientError as exc:
        raise NexError(
            f"Failed to generate pull request preview: {exc.message}",
            exit_code=ExitCode.BACKEND_UNAVAILABLE,
        ) from exc

    final_title = title or preview.get("suggested_title") or f"Changes from {head_branch}"
    final_body = body or preview.get("suggested_body") or ""
    fingerprint = preview.get("preview_fingerprint")
    commits = preview.get("commits", [])
    changed_files = preview.get("changed_files", [])
    additions = preview.get("additions", 0)
    deletions = preview.get("deletions", 0)
    has_conflicts = preview.get("has_conflicts", False)

    # 2. Display Cyber Brutalist Terminal Preview
    if not cli_ctx.json_mode:
        console.print()
        cli_ctx.output.print_banner(
            "Pull Request Preview",
            f"{repo_full_name} • {head_branch} → {base_branch}",
        )

        preview_table = Table(
            box=box.SIMPLE_HEAVY,
            show_header=False,
            padding=(0, 1),
        )
        preview_table.add_column("Field", style="bold #A1A1B5", width=18)
        preview_table.add_column("Value", style="#F1F1F5")

        preview_table.add_row("Repository", f"[bold #00D9FF]{repo_full_name}[/bold #00D9FF]")
        preview_table.add_row("Branches", f"[bold #8B5CF6]{head_branch}[/bold #8B5CF6] → [bold #00D9FF]{base_branch}[/bold #00D9FF]")
        preview_table.add_row("Title", f"[bold #F1F1F5]{final_title}[/bold #F1F1F5]")
        preview_table.add_row("Draft Mode", "[#F59E0B]Yes (Draft PR)[/#F59E0B]" if draft else "[#10B981]No (Ready for Review)[/#10B981]")
        preview_table.add_row("Commits", f"[bold #F1F1F5]{len(commits)}[/bold #F1F1F5] commit(s)")
        preview_table.add_row("Diff Stats", f"[#10B981]+{additions}[/#10B981] / [#EF4444]-{deletions}[/#EF4444] across {len(changed_files)} file(s)")
        preview_table.add_row(
            "Merge Conflicts",
            "[bold #EF4444]POTENTIAL CONFLICTS DETECTED[/bold #EF4444]" if has_conflicts else "[bold #10B981]CLEAN (No Conflicts)[/bold #10B981]",
        )
        preview_table.add_row("Risk Level", "[bold #EF4444]CRITICAL[/bold #EF4444]")

        console.print(preview_table)

        if changed_files:
            console.print("  [bold #A1A1B5]Changed Files:[/bold #A1A1B5]")
            for f in changed_files[:10]:
                console.print(f"    • [#F1F1F5]{f.get('filename')}[/#F1F1F5] [dim](+{f.get('additions', 0)} / -{f.get('deletions', 0)})[/dim]")
            if len(changed_files) > 10:
                console.print(f"    [dim]... and {len(changed_files) - 10} more files[/dim]")
        console.print()

    # 3. Handle --dry-run
    if dry_run:
        dry_run_data = {
            "dry_run": True,
            "repository": repo_full_name,
            "title": final_title,
            "body": final_body,
            "head": head_branch,
            "base": base_branch,
            "draft": draft,
            "commits_count": len(commits),
            "additions": additions,
            "deletions": deletions,
            "changed_files_count": len(changed_files),
            "preview_fingerprint": fingerprint,
        }
        if cli_ctx.json_mode:
            print_json_success("pr.create", dry_run_data, cli_ctx.correlation_id)
            return

        cli_ctx.output.print_info(
            "[DRY-RUN] Pull request comparison verified. No PR was published to GitHub."
        )
        return

    # 4. Enforce CRITICAL Risk Human Approval Policy
    ApprovalPolicy.request_approval(
        f"Publish pull request '{final_title}' ({head_branch} → {base_branch}) to GitHub?",
        operation_name="create_pull_request",
        risk_level=RiskLevel.CRITICAL,
        yes_flag=cli_ctx.yes,
    )

    # 5. Create Pull Request via Backend GitHub App Service
    create_payload = {
        "title": final_title,
        "body": final_body,
        "head": head_branch,
        "base": base_branch,
        "draft": draft,
        "preview_fingerprint": fingerprint,
        "approved": True,
    }

    try:
        pr_record = cli_ctx.client.request(
            "POST",
            f"/repositories/{repo_id}/pulls/",
            json=create_payload,
        )
    except NexClientError as exc:
        raise NexError(
            f"Failed to publish pull request to GitHub: {exc.message}",
            exit_code=ExitCode.BACKEND_UNAVAILABLE,
        ) from exc

    if cli_ctx.json_mode:
        print_json_success("pr.create", pr_record, cli_ctx.correlation_id)
        return

    # 6. Render Cyber Brutalist Success Summary
    pr_num = pr_record.get("number", "N/A")
    pr_url = pr_record.get("html_url", "")
    pr_state = pr_record.get("state", "open").upper()
    is_pr_draft = pr_record.get("draft", False)

    state_badge = (
        "[#F59E0B]DRAFT[/#F59E0B]"
        if is_pr_draft
        else f"[#10B981]{pr_state}[/#10B981]"
    )

    success_content = f"""[bold #10B981]✓ Pull Request #{pr_num} Published Successfully[/bold #10B981]

[bold #A1A1B5]TITLE:[/bold #A1A1B5]    [bold #F1F1F5]{pr_record.get('title')}[/bold #F1F1F5]
[bold #A1A1B5]BRANCHES:[/bold #A1A1B5] [bold #8B5CF6]{pr_record.get('head_branch')}[/bold #8B5CF6] → [bold #00D9FF]{pr_record.get('base_branch')}[/bold #00D9FF]
[bold #A1A1B5]STATUS:[/bold #A1A1B5]   {state_badge}
[bold #A1A1B5]GITHUB:[/bold #A1A1B5]   [link={pr_url}]{pr_url}[/link]
"""
    panel = Panel(
        success_content.strip(),
        title="[bold #F1F1F5]GITHUB PULL REQUEST[/bold #F1F1F5]",
        border_style="#10B981",
        padding=(1, 2),
    )
    console.print()
    console.print(panel)
    console.print()


# Alias for backwards compatibility
pr = pr_root


@app.command(name="list")
def list_pull_requests(
    ctx: typer.Context,
    state: Annotated[
        str,
        typer.Option("--state", "-s", help="Filter by PR state: 'open', 'closed', 'merged', or 'all'."),
    ] = "open",
    repo: Annotated[
        str | None,
        typer.Option("--repo", "-R", help="Target repository UUID or owner/name slug."),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Maximum number of pull requests to display."),
    ] = 30,
) -> None:
    """List pull requests for a synchronized GitHub repository."""
    cli_ctx: CLIContext = ctx.obj
    _require_auth()

    repo_root = cli_ctx.repo_root if not repo else None
    if repo_root:
        try:
            repo_root = _ensure_git_repo(cli_ctx)
        except NexRepositoryError:
            repo_root = None

    repo_data = _resolve_repo(cli_ctx, repo, repo_root)
    repo_id = str(repo_data["id"])
    repo_full_name = repo_data.get("full_name", "unknown")

    params: dict[str, Any] = {"page_size": limit}
    if state.lower() != "all":
        params["state"] = state.lower()

    try:
        res = cli_ctx.client.request("GET", f"/repositories/{repo_id}/pulls/", params=params)
        prs = res.get("results", []) if isinstance(res, dict) else res
    except NexClientError as exc:
        raise NexError(
            f"Failed to fetch pull requests: {exc.message}",
            exit_code=ExitCode.BACKEND_UNAVAILABLE,
        ) from exc

    if cli_ctx.json_mode:
        print_json_success(
            "pr.list",
            {"count": len(prs), "repository": repo_full_name, "pull_requests": prs},
            cli_ctx.correlation_id,
        )
        return

    console.print()
    if not prs:
        console.print(f"[#A1A1B5]No pull requests found for [bold #00D9FF]{repo_full_name}[/bold #00D9FF] matching state '{state}'.[/#A1A1B5]\n")
        return

    table = Table(
        title=f"[bold #00D9FF]PULL REQUESTS — {repo_full_name}[/bold #00D9FF]",
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold #A1A1B5",
    )
    table.add_column("#", style="bold #00D9FF", justify="right", width=6)
    table.add_column("Title", style="bold #F1F1F5")
    table.add_column("Branches", style="dim")
    table.add_column("Author", style="#A1A1B5")
    table.add_column("Status", justify="center")
    table.add_column("Updated", style="dim")

    for p in prs:
        num = f"#{p.get('number')}"
        t = p.get("title", "")
        if p.get("draft"):
            t = f"[dim](Draft)[/dim] {t}"
        branches = f"{p.get('head_branch')} → {p.get('base_branch')}"
        author = p.get("author_username") or "unknown"
        st = p.get("state", "open").upper()
        if p.get("draft"):
            status_tag = "[#F59E0B]DRAFT[/#F59E0B]"
        elif st == "OPEN":
            status_tag = "[#10B981]OPEN[/#10B981]"
        elif st == "MERGED":
            status_tag = "[#8B5CF6]MERGED[/#8B5CF6]"
        else:
            status_tag = "[#EF4444]CLOSED[/#EF4444]"

        updated = (p.get("github_updated_at") or p.get("updated_at") or "")[:10]
        table.add_row(num, t, branches, author, status_tag, updated)

    console.print(table)
    console.print(f"  [dim]Total: {len(prs)} pull request(s) displayed.[/dim]\n")


@app.command(name="view")
def view_pull_request(
    ctx: typer.Context,
    number: Annotated[int, typer.Argument(help="Pull request number.")],
    repo: Annotated[
        str | None,
        typer.Option("--repo", "-R", help="Target repository UUID or owner/name slug."),
    ] = None,
    sync: Annotated[
        bool,
        typer.Option("--sync", "-s", help="Synchronize live state from GitHub API before viewing."),
    ] = False,
) -> None:
    """Inspect full details and state for a specific pull request."""
    cli_ctx: CLIContext = ctx.obj
    _require_auth()

    repo_root = cli_ctx.repo_root if not repo else None
    if repo_root:
        try:
            repo_root = _ensure_git_repo(cli_ctx)
        except NexRepositoryError:
            repo_root = None

    repo_data = _resolve_repo(cli_ctx, repo, repo_root)
    repo_id = str(repo_data["id"])
    repo_full_name = repo_data.get("full_name", "unknown")

    try:
        if sync:
            pr_data = cli_ctx.client.request(
                "POST", f"/repositories/{repo_id}/pulls/{number}/sync/"
            )
        else:
            pr_data = cli_ctx.client.request(
                "GET", f"/repositories/{repo_id}/pulls/{number}/"
            )
    except NexClientError as exc:
        raise NexError(
            f"Failed to fetch pull request #{number}: {exc.message}",
            exit_code=ExitCode.BACKEND_UNAVAILABLE,
        ) from exc

    if cli_ctx.json_mode:
        print_json_success("pr.view", pr_data, cli_ctx.correlation_id)
        return

    console.print()
    pr_title = pr_data.get("title", "")
    pr_state = pr_data.get("state", "open").upper()
    is_draft = pr_data.get("draft", False)
    head_b = pr_data.get("head_branch", "")
    base_b = pr_data.get("base_branch", "")
    author = pr_data.get("author_username", "unknown")
    html_url = pr_data.get("html_url", "")
    body_text = pr_data.get("body") or "[dim]No description provided.[/dim]"
    commits_cnt = pr_data.get("commits_count", 0)
    adds = pr_data.get("additions", 0)
    dels = pr_data.get("deletions", 0)
    changed_f = pr_data.get("changed_files_count", 0)

    if is_draft:
        st_tag = "[#F59E0B]DRAFT[/#F59E0B]"
    elif pr_state == "OPEN":
        st_tag = "[#10B981]OPEN[/#10B981]"
    elif pr_state == "MERGED":
        st_tag = "[#8B5CF6]MERGED[/#8B5CF6]"
    else:
        st_tag = "[#EF4444]CLOSED[/#EF4444]"

    content = f"""[bold #00D9FF]#{number}: {pr_title}[/bold #00D9FF] ({st_tag})
[bold #A1A1B5]Branches:[/bold #A1A1B5]  [bold #8B5CF6]{head_b}[/bold #8B5CF6] → [bold #00D9FF]{base_b}[/bold #00D9FF]
[bold #A1A1B5]Author:[/bold #A1A1B5]    {author}
[bold #A1A1B5]URL:[/bold #A1A1B5]       [link={html_url}]{html_url}[/link]
[bold #A1A1B5]Stats:[/bold #A1A1B5]     {commits_cnt} commit(s), [#10B981]+{adds}[/#10B981] / [#EF4444]-{dels}[/#EF4444] in {changed_f} file(s)

[bold #A1A1B5]DESCRIPTION[/bold #A1A1B5]
{body_text}
"""
    panel = Panel(
        content.strip(),
        title=f"[bold #F1F1F5]{repo_full_name} • PR #{number}[/bold #F1F1F5]",
        border_style="#00D9FF",
        padding=(1, 2),
    )
    console.print(panel)
    console.print()
