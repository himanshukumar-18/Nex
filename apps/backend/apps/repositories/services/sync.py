"""NEX Repositories — GitHub Repository Synchronization Service.

Discovers, paginates, and synchronizes repositories accessible to authorized
GitHub App installations. Performs idempotent upserts, tracks lifecycle changes,
and preserves deleted/unlinked repositories with safe tombstoning (is_active=False).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from django.db import transaction
from django.utils import timezone as django_timezone

from apps.accounts.models import User
from apps.audit_logs.models import SecurityAuditEvent
from apps.repositories.models import GitHubInstallation, Repository
from apps.repositories.services.github_app import (
    GITHUB_API_BASE_URL,
    GitHubAppError,
    GitHubAppService,
)

logger = logging.getLogger(__name__)

MAX_PAGES = 50
PER_PAGE = 100


class RepositorySyncError(GitHubAppError):
    """Raised when repository synchronization fails."""


class RepositorySyncService:
    """Manages repository discovery and synchronization from GitHub."""

    @classmethod
    def sync_installation_repositories(
        cls,
        installation: GitHubInstallation,
    ) -> dict[str, Any]:
        """Fetch and synchronize all repositories accessible to a GitHub installation.

        Args:
            installation: Authorized GitHubInstallation instance.

        Returns:
            Dictionary with synchronization statistics: total, added, updated, removed.

        Raises:
            RepositorySyncError: If token retrieval or GitHub API communication fails.
        """
        if not installation.is_active:
            raise RepositorySyncError(
                f"Cannot sync inactive installation {installation.installation_id} (status: {installation.status})."
            )

        token = GitHubAppService.get_installation_access_token(installation.installation_id)
        headers = GitHubAppService.get_headers(token=token)

        fetched_repos: list[dict[str, Any]] = []
        page = 1

        try:
            with httpx.Client(timeout=15.0) as client:
                while page <= MAX_PAGES:
                    url = f"{GITHUB_API_BASE_URL}/installation/repositories?per_page={PER_PAGE}&page={page}"
                    response = client.get(url, headers=headers)

                    if response.status_code == 401:
                        # Cached token may have expired or revoked; force refresh once
                        token = GitHubAppService.get_installation_access_token(
                            installation.installation_id, force_refresh=True
                        )
                        headers = GitHubAppService.get_headers(token=token)
                        response = client.get(url, headers=headers)

                    if response.is_error:
                        raise RepositorySyncError(
                            f"GitHub API error fetching repositories (HTTP {response.status_code}): {response.text}"
                        )

                    payload = response.json()
                    repos = payload.get("repositories", [])
                    total_count = payload.get("total_count", len(repos))

                    fetched_repos.extend(repos)

                    if len(repos) < PER_PAGE or len(fetched_repos) >= total_count:
                        break

                    page += 1

        except httpx.RequestError as exc:
            raise RepositorySyncError(f"Network error syncing repositories: {exc}") from exc

        # Process and persist repositories atomically
        now = django_timezone.now()
        added = 0
        updated = 0
        fetched_ids: set[int] = set()

        with transaction.atomic():
            for repo in fetched_repos:
                repo_id = repo.get("id")
                if not repo_id:
                    continue

                fetched_ids.add(repo_id)
                owner_info = repo.get("owner", {})
                permissions_info = repo.get("permissions", {})

                repo_obj, created = Repository.objects.update_or_create(
                    github_repo_id=repo_id,
                    defaults={
                        "installation": installation,
                        "owner": installation.user,
                        "name": repo.get("name", ""),
                        "full_name": repo.get("full_name", ""),
                        "owner_login": owner_info.get("login", installation.account_login),
                        "owner_type": owner_info.get("type", installation.account_type),
                        "description": repo.get("description") or "",
                        "is_private": repo.get("private", False),
                        "is_fork": repo.get("fork", False),
                        "is_archived": repo.get("archived", False),
                        "default_branch": repo.get("default_branch") or "main",
                        "language": repo.get("language") or "",
                        "html_url": repo.get("html_url") or "",
                        "clone_url": repo.get("clone_url") or "",
                        "ssh_url": repo.get("ssh_url") or "",
                        "permissions": permissions_info,
                        "is_active": True,
                        "sync_status": Repository.SyncStatus.SYNCED,
                        "sync_error": "",
                        "last_synced_at": now,
                        "metadata": {
                            "stargazers_count": repo.get("stargazers_count", 0),
                            "open_issues_count": repo.get("open_issues_count", 0),
                            "size": repo.get("size", 0),
                            "topics": repo.get("topics", []),
                        },
                    },
                )

                if created:
                    added += 1
                else:
                    updated += 1

            # Deactivate omitted repositories (tombstoning without deletion)
            to_remove = Repository.objects.filter(
                installation=installation,
                is_active=True,
            ).exclude(github_repo_id__in=fetched_ids)

            removed = to_remove.count()
            if removed > 0:
                to_remove.update(
                    is_active=False,
                    sync_status=Repository.SyncStatus.REMOVED,
                    last_synced_at=now,
                    updated_at=now,
                )

            installation.last_synced_at = now
            installation.save(update_fields=["last_synced_at", "updated_at"])

        SecurityAuditEvent.record(
            SecurityAuditEvent.EventType.GITHUB_REPOSITORIES_SYNCED,
            user=installation.user,
            metadata={
                "installation_id": installation.installation_id,
                "account_login": installation.account_login,
                "total": len(fetched_repos),
                "added": added,
                "updated": updated,
                "removed": removed,
            },
        )

        logger.info(
            "Synced repositories for installation %s: total=%d, added=%d, updated=%d, removed=%d",
            installation.installation_id,
            len(fetched_repos),
            added,
            updated,
            removed,
        )

        return {
            "installation_id": installation.installation_id,
            "total": len(fetched_repos),
            "added": added,
            "updated": updated,
            "removed": removed,
            "synced_at": now.isoformat(),
        }

    @classmethod
    def sync_user_repositories(
        cls,
        user: User,
        installation_id: int | None = None,
    ) -> dict[str, Any]:
        """Synchronize repositories across all or a specific active installation for a user.

        Args:
            user: Authenticated NEX user.
            installation_id: Optional specific installation ID to synchronize.

        Returns:
            Aggregated sync statistics.
        """
        installations = GitHubInstallation.objects.filter(
            user=user,
            status=GitHubInstallation.Status.ACTIVE,
        )

        if installation_id:
            installations = installations.filter(installation_id=installation_id)

        now = django_timezone.now()
        total_repos = 0
        total_added = 0
        total_updated = 0
        total_removed = 0
        installations_synced = 0

        for inst in installations:
            try:
                stats = cls.sync_installation_repositories(inst)
                total_repos += stats["total"]
                total_added += stats["added"]
                total_updated += stats["updated"]
                total_removed += stats["removed"]
                installations_synced += 1
            except Exception as exc:
                logger.exception(
                    "Failed to sync repositories for installation %s: %s",
                    inst.installation_id,
                    exc,
                )

        return {
            "total": total_repos,
            "added": total_added,
            "updated": total_updated,
            "removed": total_removed,
            "installations_synced": installations_synced,
            "synced_at": now.isoformat(),
        }
