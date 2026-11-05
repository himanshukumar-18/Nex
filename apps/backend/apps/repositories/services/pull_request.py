"""NEX Repositories — GitHub Pull Request Service.

Handles Pull Request pre-flight checks, compare diffs, fingerprint-bound previews,
idempotent PR publishing via GitHub App installation tokens, status refreshes, and
webhook-driven lifecycle state synchronization.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import httpx
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone as django_timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit_logs.models import SecurityAuditEvent
from apps.repositories.models import GitHubInstallation, PullRequest, Repository
from apps.repositories.services.github_app import (
    GITHUB_API_BASE_URL,
    GitHubAppError,
    GitHubAppService,
)

logger = logging.getLogger(__name__)

PREVIEW_CACHE_TTL = 900  # 15 minutes


class PullRequestService:
    """Manages GitHub Pull Request operations, previews, and persistent synchronization."""

    @classmethod
    def _compute_preview_fingerprint(
        cls,
        repository_id: str,
        base_branch: str,
        head_branch: str,
        base_commit_sha: str,
        head_commit_sha: str,
        commit_count: int,
    ) -> str:
        """Calculate a deterministic SHA-256 fingerprint for a PR preview."""
        raw = f"{repository_id}:{base_branch}:{head_branch}:{base_commit_sha}:{head_commit_sha}:{commit_count}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @classmethod
    def preview_pull_request(
        cls,
        user: Any,
        repository: Repository,
        head_branch: str,
        base_branch: str | None = None,
        correlation_id: str = "no-correlation-id",
    ) -> dict[str, Any]:
        """Compare head and base branches via GitHub API and generate bound preview fingerprint."""
        if not repository.is_active:
            raise ValidationError(f"Repository '{repository.full_name}' is inactive or removed.")

        if repository.owner != user:
            raise PermissionDenied("You do not have permission to create pull requests for this repository.")

        installation = repository.installation
        if not installation or installation.status != GitHubInstallation.Status.ACTIVE:
            raise ValidationError("GitHub App installation is not connected or active.")

        base = (base_branch or repository.default_branch or "main").strip()
        head = head_branch.strip()

        if not head:
            raise ValidationError("Head branch name cannot be empty.")
        if not base:
            raise ValidationError("Base branch name cannot be empty.")
        if head == base:
            raise ValidationError(f"Head branch and base branch cannot be identical ('{head}').")

        # Obtain GitHub installation token
        token = GitHubAppService.get_installation_access_token(installation.installation_id)
        headers = GitHubAppService.get_headers(token=token)

        owner, repo_name = repository.owner_login, repository.name
        url = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo_name}/compare/{base}...{head}"

        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.get(url, headers=headers)
                if res.status_code == 404:
                    raise ValidationError(
                        f"Either base branch '{base}' or head branch '{head}' does not exist on GitHub remote."
                    )
                if res.is_error:
                    raise ValidationError(f"GitHub compare API returned HTTP {res.status_code}: {res.text}")

                data = res.json()
        except httpx.RequestError as exc:
            raise ValidationError(f"Network error communicating with GitHub: {exc}") from exc

        commits_raw = data.get("commits", [])
        files_raw = data.get("files", [])

        ahead_by = data.get("ahead_by", len(commits_raw))
        behind_by = data.get("behind_by", 0)
        status = data.get("status", "ahead")

        base_commit_sha = (
            data.get("base_commit", {}).get("sha", "")
            if isinstance(data.get("base_commit"), dict)
            else ""
        )
        head_commit_sha = commits_raw[-1]["sha"] if commits_raw else ""

        fingerprint = cls._compute_preview_fingerprint(
            repository_id=str(repository.id),
            base_branch=base,
            head_branch=head,
            base_commit_sha=base_commit_sha,
            head_commit_sha=head_commit_sha,
            commit_count=len(commits_raw),
        )

        commits_summary = [
            {
                "sha": c.get("sha", "")[:7],
                "full_sha": c.get("sha", ""),
                "message": (
                    c.get("commit", {}).get("message", "").split("\n")[0]
                    if isinstance(c.get("commit"), dict)
                    else ""
                ),
                "author": (
                    c.get("commit", {}).get("author", {}).get("name", "")
                    if isinstance(c.get("commit"), dict)
                    else ""
                ),
                "date": (
                    c.get("commit", {}).get("author", {}).get("date", "")
                    if isinstance(c.get("commit"), dict)
                    else ""
                ),
            }
            for c in commits_raw
        ]

        files_summary = [
            {
                "filename": f.get("filename", ""),
                "status": f.get("status", "modified"),
                "additions": f.get("additions", 0),
                "deletions": f.get("deletions", 0),
                "changes": f.get("changes", 0),
            }
            for f in files_raw
        ]

        preview_payload = {
            "repository": {
                "id": str(repository.id),
                "name": repository.name,
                "full_name": repository.full_name,
                "default_branch": repository.default_branch,
            },
            "base": base,
            "head": head,
            "status": status,
            "ahead_by": ahead_by,
            "behind_by": behind_by,
            "total_commits": len(commits_raw),
            "total_files": len(files_raw),
            "total_additions": sum(f.get("additions", 0) for f in files_raw),
            "total_deletions": sum(f.get("deletions", 0) for f in files_raw),
            "commits": commits_summary,
            "files": files_summary,
            "preview_fingerprint": fingerprint,
        }

        # Cache preview in Redis to bind developer approval
        cache_key = f"pr_preview:{fingerprint}"
        cache.set(cache_key, preview_payload, timeout=PREVIEW_CACHE_TTL)

        return preview_payload

    @classmethod
    def create_pull_request(
        cls,
        user: Any,
        repository: Repository,
        title: str,
        head_branch: str,
        base_branch: str,
        body: str = "",
        draft: bool = False,
        preview_fingerprint: str | None = None,
        approved: bool = False,
        correlation_id: str = "no-correlation-id",
        ip_address: str | None = None,
    ) -> PullRequest:
        """Create and publish a Pull Request through GitHub App after validating approval and fingerprint."""
        if not approved:
            raise ValidationError("Explicit developer approval is required to create a Pull Request.")

        clean_title = title.strip()
        if not clean_title:
            raise ValidationError("Pull request title cannot be empty.")

        clean_head = head_branch.strip()
        clean_base = base_branch.strip()

        if repository.owner != user:
            raise PermissionDenied("You do not have permission to create pull requests for this repository.")

        installation = repository.installation
        if not installation or installation.status != GitHubInstallation.Status.ACTIVE:
            raise ValidationError("GitHub App installation is not connected or active.")

        # Validate fingerprint if supplied
        if preview_fingerprint:
            cache_key = f"pr_preview:{preview_fingerprint}"
            cached_preview = cache.get(cache_key)
            if not cached_preview:
                raise ValidationError(
                    "The PR preview has expired or is invalid. Please preview changes again before creating the PR."
                )
            if (
                cached_preview.get("head") != clean_head
                or cached_preview.get("base") != clean_base
                or cached_preview.get("repository", {}).get("id") != str(repository.id)
            ):
                raise ValidationError("Supplied PR parameters do not match the approved preview fingerprint.")

        # Idempotency check: verify if an open PR already exists in DB
        existing_pr = PullRequest.objects.filter(
            repository=repository,
            head_branch=clean_head,
            base_branch=clean_base,
            state=PullRequest.State.OPEN,
        ).first()
        if existing_pr:
            return existing_pr

        token = GitHubAppService.get_installation_access_token(installation.installation_id)
        headers = GitHubAppService.get_headers(token=token)

        owner, repo_name = repository.owner_login, repository.name
        url = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo_name}/pulls"

        req_body: dict[str, Any] = {
            "title": clean_title,
            "head": clean_head,
            "base": clean_base,
            "body": body,
            "draft": draft,
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.post(url, headers=headers, json=req_body)

                if res.status_code == 422:
                    err_json = res.json() if res.content else {}
                    msg = err_json.get("message", "Validation failed on GitHub")
                    errors = err_json.get("errors", [])
                    detail_str = "; ".join(e.get("message", "") for e in errors if isinstance(e, dict))
                    raise ValidationError(f"GitHub rejected pull request: {msg}. {detail_str}".strip())

                if res.is_error:
                    raise ValidationError(f"GitHub API error creating pull request (HTTP {res.status_code}): {res.text}")

                pr_data = res.json()
        except httpx.RequestError as exc:
            raise ValidationError(f"Network error communicating with GitHub: {exc}") from exc

        # Create or update PullRequest record in PostgreSQL
        pr_record, _ = PullRequest.objects.update_or_create(
            github_pr_id=pr_data["id"],
            defaults={
                "user": user,
                "repository": repository,
                "installation": installation,
                "number": pr_data["number"],
                "title": pr_data.get("title", clean_title),
                "body": pr_data.get("body", "") or "",
                "base_branch": pr_data.get("base", {}).get("ref", clean_base),
                "head_branch": pr_data.get("head", {}).get("ref", clean_head),
                "html_url": pr_data.get("html_url", ""),
                "state": (
                    PullRequest.State.MERGED
                    if pr_data.get("merged")
                    else PullRequest.State.CLOSED
                    if pr_data.get("state") == "closed"
                    else PullRequest.State.OPEN
                ),
                "is_draft": pr_data.get("draft", draft),
                "last_synced_at": django_timezone.now(),
                "metadata": {
                    "comments": pr_data.get("comments", 0),
                    "commits": pr_data.get("commits", 0),
                    "additions": pr_data.get("additions", 0),
                    "deletions": pr_data.get("deletions", 0),
                    "changed_files": pr_data.get("changed_files", 0),
                },
            },
        )

        # Log security audit event
        SecurityAuditEvent.objects.create(
            event_type=SecurityAuditEvent.EventType.GITHUB_PULL_REQUEST_CREATED,
            user=user,
            ip_address=ip_address,
            correlation_id=correlation_id,
            metadata={
                "repository_id": str(repository.id),
                "repository_full_name": repository.full_name,
                "pr_number": pr_record.number,
                "pr_url": pr_record.html_url,
                "head_branch": clean_head,
                "base_branch": clean_base,
                "is_draft": pr_record.is_draft,
            },
        )

        # Invalidate preview fingerprint cache after use
        if preview_fingerprint:
            cache.delete(f"pr_preview:{preview_fingerprint}")

        return pr_record

    @classmethod
    def sync_pull_request(
        cls,
        user: Any,
        repository: Repository,
        number: int,
        correlation_id: str = "no-correlation-id",
        ip_address: str | None = None,
    ) -> PullRequest:
        """Fetch live PR status from GitHub API and synchronize PostgreSQL record."""
        if repository.owner != user:
            raise PermissionDenied("You do not have permission to inspect this repository.")

        installation = repository.installation
        if not installation or installation.status != GitHubInstallation.Status.ACTIVE:
            raise ValidationError("GitHub App installation is not connected or active.")

        token = GitHubAppService.get_installation_access_token(installation.installation_id)
        headers = GitHubAppService.get_headers(token=token)

        owner, repo_name = repository.owner_login, repository.name
        url = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo_name}/pulls/{number}"

        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.get(url, headers=headers)
                if res.status_code == 404:
                    raise ValidationError(f"Pull request #{number} was not found on GitHub.")
                if res.is_error:
                    raise ValidationError(f"GitHub API error fetching pull request (HTTP {res.status_code})")
                pr_data = res.json()
        except httpx.RequestError as exc:
            raise ValidationError(f"Network error communicating with GitHub: {exc}") from exc

        state = (
            PullRequest.State.MERGED
            if pr_data.get("merged")
            else PullRequest.State.CLOSED
            if pr_data.get("state") == "closed"
            else PullRequest.State.OPEN
        )

        pr_record, _ = PullRequest.objects.update_or_create(
            github_pr_id=pr_data["id"],
            defaults={
                "user": user,
                "repository": repository,
                "installation": installation,
                "number": pr_data["number"],
                "title": pr_data.get("title", f"Pull Request #{number}"),
                "body": pr_data.get("body", "") or "",
                "base_branch": pr_data.get("base", {}).get("ref", repository.default_branch),
                "head_branch": pr_data.get("head", {}).get("ref", "unknown"),
                "html_url": pr_data.get("html_url", ""),
                "state": state,
                "is_draft": pr_data.get("draft", False),
                "merged_at": pr_data.get("merged_at"),
                "closed_at": pr_data.get("closed_at"),
                "last_synced_at": django_timezone.now(),
                "metadata": {
                    "comments": pr_data.get("comments", 0),
                    "commits": pr_data.get("commits", 0),
                    "additions": pr_data.get("additions", 0),
                    "deletions": pr_data.get("deletions", 0),
                    "changed_files": pr_data.get("changed_files", 0),
                },
            },
        )

        SecurityAuditEvent.objects.create(
            event_type=SecurityAuditEvent.EventType.GITHUB_PULL_REQUEST_SYNCED,
            user=user,
            ip_address=ip_address,
            correlation_id=correlation_id,
            metadata={
                "repository_id": str(repository.id),
                "pr_number": pr_record.number,
                "state": state,
            },
        )

        return pr_record

    @classmethod
    def sync_from_webhook(cls, payload: dict[str, Any], action: str) -> PullRequest | None:
        """Handle incoming 'pull_request' webhook event and update database record."""
        repo_data = payload.get("repository", {})
        github_repo_id = repo_data.get("id")
        if not github_repo_id:
            return None

        repository = Repository.objects.filter(github_repo_id=github_repo_id).first()
        if not repository:
            return None

        pr_data = payload.get("pull_request", {})
        if not pr_data or "id" not in pr_data:
            return None

        state = (
            PullRequest.State.MERGED
            if pr_data.get("merged")
            else PullRequest.State.CLOSED
            if pr_data.get("state") == "closed" or action == "closed"
            else PullRequest.State.OPEN
        )

        pr_record, _ = PullRequest.objects.update_or_create(
            github_pr_id=pr_data["id"],
            defaults={
                "user": repository.owner,
                "repository": repository,
                "installation": repository.installation,
                "number": pr_data["number"],
                "title": pr_data.get("title", ""),
                "body": pr_data.get("body", "") or "",
                "base_branch": pr_data.get("base", {}).get("ref", repository.default_branch),
                "head_branch": pr_data.get("head", {}).get("ref", ""),
                "html_url": pr_data.get("html_url", ""),
                "state": state,
                "is_draft": pr_data.get("draft", False),
                "merged_at": pr_data.get("merged_at"),
                "closed_at": pr_data.get("closed_at"),
                "last_synced_at": django_timezone.now(),
                "metadata": {
                    "action": action,
                    "comments": pr_data.get("comments", 0),
                    "commits": pr_data.get("commits", 0),
                    "additions": pr_data.get("additions", 0),
                    "deletions": pr_data.get("deletions", 0),
                },
            },
        )
        return pr_record
