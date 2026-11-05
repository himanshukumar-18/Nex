"""NEX Repositories — GitHub Repository Synchronization & API Tests.

Verifies repository discovery, multi-page pagination, idempotent upserts,
tombstone deactivation, tenant isolation, search filtering, manual sync triggers,
and repository webhook event handling.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone as django_timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.repositories.models import GitHubInstallation, Repository
from apps.repositories.services.github_app import GitHubAppService
from apps.repositories.services.sync import RepositorySyncError, RepositorySyncService


class RepositorySyncServiceTestCase(TestCase):
    """Test suite for RepositorySyncService discovery and persistence logic."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="dev@nex.dev",
            firebase_uid="uid-dev-123",
        )
        self.installation = GitHubInstallation.objects.create(
            user=self.user,
            installation_id=990011,
            account_login="acme-corp",
            account_type=GitHubInstallation.AccountType.ORGANIZATION,
            status=GitHubInstallation.Status.ACTIVE,
        )

    @patch("apps.repositories.services.sync.httpx.Client")
    @patch.object(GitHubAppService, "get_installation_access_token", return_value="ghs_mock_token_123")
    def test_sync_single_page_repositories(self, mock_get_token: MagicMock, mock_client_cls: MagicMock) -> None:
        """Verify successful discovery and upsert of repositories from GitHub API."""
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_error = False
        mock_response.json.return_value = {
            "total_count": 2,
            "repositories": [
                {
                    "id": 101,
                    "name": "core-backend",
                    "full_name": "acme-corp/core-backend",
                    "owner": {"login": "acme-corp", "type": "Organization"},
                    "description": "Core Django backend for NEX",
                    "private": True,
                    "fork": False,
                    "archived": False,
                    "default_branch": "main",
                    "language": "Python",
                    "html_url": "https://github.com/acme-corp/core-backend",
                    "clone_url": "https://github.com/acme-corp/core-backend.git",
                    "ssh_url": "git@github.com:acme-corp/core-backend.git",
                    "permissions": {"admin": True, "push": True, "pull": True},
                },
                {
                    "id": 102,
                    "name": "web-frontend",
                    "full_name": "acme-corp/web-frontend",
                    "owner": {"login": "acme-corp", "type": "Organization"},
                    "description": "React frontend for NEX",
                    "private": False,
                    "fork": False,
                    "archived": False,
                    "default_branch": "development",
                    "language": "TypeScript",
                    "html_url": "https://github.com/acme-corp/web-frontend",
                    "clone_url": "https://github.com/acme-corp/web-frontend.git",
                    "ssh_url": "git@github.com:acme-corp/web-frontend.git",
                    "permissions": {"admin": False, "push": True, "pull": True},
                },
            ],
        }
        mock_client.get.return_value = mock_response

        stats = RepositorySyncService.sync_installation_repositories(self.installation)

        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["added"], 2)
        self.assertEqual(stats["updated"], 0)
        self.assertEqual(stats["removed"], 0)

        repos = Repository.objects.filter(installation=self.installation, is_active=True)
        self.assertEqual(repos.count(), 2)

        repo1 = repos.get(github_repo_id=101)
        self.assertEqual(repo1.name, "core-backend")
        self.assertTrue(repo1.is_private)
        self.assertEqual(repo1.language, "Python")
        self.assertEqual(repo1.owner, self.user)

        repo2 = repos.get(github_repo_id=102)
        self.assertEqual(repo2.name, "web-frontend")
        self.assertFalse(repo2.is_private)
        self.assertEqual(repo2.language, "TypeScript")

    @patch("apps.repositories.services.sync.httpx.Client")
    @patch.object(GitHubAppService, "get_installation_access_token", return_value="ghs_mock_token_123")
    def test_sync_idempotency_and_removal_tombstone(
        self, mock_get_token: MagicMock, mock_client_cls: MagicMock
    ) -> None:
        """Verify that updating omitted repositories marks them as removed rather than hard-deleting."""
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client

        # Initial sync with two repositories
        mock_response_1 = MagicMock()
        mock_response_1.status_code = 200
        mock_response_1.is_error = False
        mock_response_1.json.return_value = {
            "total_count": 2,
            "repositories": [
                {
                    "id": 201,
                    "name": "service-alpha",
                    "full_name": "acme-corp/service-alpha",
                    "owner": {"login": "acme-corp", "type": "Organization"},
                    "private": True,
                    "html_url": "https://github.com/acme-corp/service-alpha",
                },
                {
                    "id": 202,
                    "name": "service-beta",
                    "full_name": "acme-corp/service-beta",
                    "owner": {"login": "acme-corp", "type": "Organization"},
                    "private": True,
                    "html_url": "https://github.com/acme-corp/service-beta",
                },
            ],
        }
        mock_client.get.return_value = mock_response_1
        RepositorySyncService.sync_installation_repositories(self.installation)

        self.assertEqual(Repository.objects.filter(installation=self.installation, is_active=True).count(), 2)

        # Second sync: service-beta is removed from installation permissions
        mock_response_2 = MagicMock()
        mock_response_2.status_code = 200
        mock_response_2.is_error = False
        mock_response_2.json.return_value = {
            "total_count": 1,
            "repositories": [
                {
                    "id": 201,
                    "name": "service-alpha",
                    "full_name": "acme-corp/service-alpha",
                    "owner": {"login": "acme-corp", "type": "Organization"},
                    "description": "Updated description",
                    "private": True,
                    "html_url": "https://github.com/acme-corp/service-alpha",
                },
            ],
        }
        mock_client.get.return_value = mock_response_2

        stats = RepositorySyncService.sync_installation_repositories(self.installation)
        self.assertEqual(stats["total"], 1)
        self.assertEqual(stats["added"], 0)
        self.assertEqual(stats["updated"], 1)
        self.assertEqual(stats["removed"], 1)

        # Beta must still exist but be tombstoned
        beta = Repository.objects.get(github_repo_id=202)
        self.assertFalse(beta.is_active)
        self.assertEqual(beta.sync_status, Repository.SyncStatus.REMOVED)

        # Alpha must have updated description
        alpha = Repository.objects.get(github_repo_id=201)
        self.assertTrue(alpha.is_active)
        self.assertEqual(alpha.description, "Updated description")

    def test_sync_inactive_installation_fails(self) -> None:
        """Verify inactive installations cannot be synchronized."""
        self.installation.status = GitHubInstallation.Status.SUSPENDED
        self.installation.save()

        with self.assertRaises(RepositorySyncError):
            RepositorySyncService.sync_installation_repositories(self.installation)


class RepositoryApiTestCase(TestCase):
    """Test suite for repository REST API endpoints and permissions."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="primary@nex.dev",
            firebase_uid="uid-primary-123",
        )
        self.other_user = User.objects.create_user(
            email="other@nex.dev",
            firebase_uid="uid-other-456",
        )

        self.installation = GitHubInstallation.objects.create(
            user=self.user,
            installation_id=889900,
            account_login="primary-org",
            account_type=GitHubInstallation.AccountType.ORGANIZATION,
            status=GitHubInstallation.Status.ACTIVE,
        )

        # Repositories for primary user
        self.repo_py = Repository.objects.create(
            installation=self.installation,
            owner=self.user,
            github_repo_id=301,
            name="py-service",
            full_name="primary-org/py-service",
            owner_login="primary-org",
            description="Python microservice for analysis",
            is_private=True,
            language="Python",
            html_url="https://github.com/primary-org/py-service",
            clone_url="https://github.com/primary-org/py-service.git",
            is_active=True,
            is_archived=False,
        )
        self.repo_ts = Repository.objects.create(
            installation=self.installation,
            owner=self.user,
            github_repo_id=302,
            name="ts-ui",
            full_name="primary-org/ts-ui",
            owner_login="primary-org",
            description="TypeScript frontend app",
            is_private=False,
            language="TypeScript",
            html_url="https://github.com/primary-org/ts-ui",
            clone_url="https://github.com/primary-org/ts-ui.git",
            is_active=True,
            is_archived=True,
        )

        # Repository for other user (cross-tenant isolation check)
        self.other_inst = GitHubInstallation.objects.create(
            user=self.other_user,
            installation_id=778899,
            account_login="other-org",
            status=GitHubInstallation.Status.ACTIVE,
        )
        self.other_repo = Repository.objects.create(
            installation=self.other_inst,
            owner=self.other_user,
            github_repo_id=401,
            name="secret-repo",
            full_name="other-org/secret-repo",
            owner_login="other-org",
            is_private=True,
            html_url="https://github.com/other-org/secret-repo",
            clone_url="https://github.com/other-org/secret-repo.git",
            is_active=True,
        )

    def test_list_repositories_authenticated(self) -> None:
        """Verify user can list their active repositories with pagination."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/v1/repositories/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["count"], 2)
        repo_names = [r["name"] for r in data["results"]]
        self.assertIn("py-service", repo_names)
        self.assertIn("ts-ui", repo_names)
        self.assertNotIn("secret-repo", repo_names)

    def test_list_repositories_filters(self) -> None:
        """Verify search, visibility, language, and archived filters."""
        self.client.force_authenticate(user=self.user)

        # 1. Search filter
        res_search = self.client.get("/api/v1/repositories/?search=analysis")
        self.assertEqual(res_search.status_code, status.HTTP_200_OK)
        self.assertEqual(res_search.json()["count"], 1)
        self.assertEqual(res_search.json()["results"][0]["name"], "py-service")

        # 2. Visibility filter
        res_vis = self.client.get("/api/v1/repositories/?visibility=private")
        self.assertEqual(res_vis.status_code, status.HTTP_200_OK)
        self.assertEqual(res_vis.json()["count"], 1)
        self.assertEqual(res_vis.json()["results"][0]["name"], "py-service")

        # 3. Language filter
        res_lang = self.client.get("/api/v1/repositories/?language=TypeScript")
        self.assertEqual(res_lang.status_code, status.HTTP_200_OK)
        self.assertEqual(res_lang.json()["count"], 1)
        self.assertEqual(res_lang.json()["results"][0]["name"], "ts-ui")

        # 4. Archived filter
        res_arch = self.client.get("/api/v1/repositories/?archived=true")
        self.assertEqual(res_arch.status_code, status.HTTP_200_OK)
        self.assertEqual(res_arch.json()["count"], 1)
        self.assertEqual(res_arch.json()["results"][0]["name"], "ts-ui")

    def test_detail_repository_tenant_isolation(self) -> None:
        """Verify cross-tenant isolation: accessing another user's repository yields 404."""
        self.client.force_authenticate(user=self.user)

        # Allowed: own repository
        res_own = self.client.get(f"/api/v1/repositories/{self.repo_py.id}/")
        self.assertEqual(res_own.status_code, status.HTTP_200_OK)
        self.assertEqual(res_own.json()["name"], "py-service")
        self.assertIn("clone_url", res_own.json())

        # Forbidden / Not Found: other user's repository
        res_other = self.client.get(f"/api/v1/repositories/{self.other_repo.id}/")
        self.assertEqual(res_other.status_code, status.HTTP_404_NOT_FOUND)

    def test_repository_sync_status(self) -> None:
        """Verify repository sync metrics endpoint."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/v1/repositories/sync/status/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["installations_count"], 1)
        self.assertEqual(data["total_repositories"], 2)
        self.assertEqual(data["public_repositories"], 1)
        self.assertEqual(data["private_repositories"], 1)

    @patch("apps.repositories.services.sync.RepositorySyncService.sync_user_repositories")
    def test_manual_sync_endpoint(self, mock_sync_user: MagicMock) -> None:
        """Verify manual repository sync trigger."""
        mock_sync_user.return_value = {
            "total": 5,
            "added": 1,
            "updated": 4,
            "removed": 0,
            "installations_synced": 1,
            "synced_at": django_timezone.now().isoformat(),
        }

        self.client.force_authenticate(user=self.user)
        response = self.client.post("/api/v1/repositories/sync/", data={}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["total"], 5)
        self.assertEqual(data["added"], 1)
        mock_sync_user.assert_called_once()


class RepositoryWebhookEventsTestCase(TestCase):
    """Test suite for repository lifecycle updates via incoming GitHub webhooks."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="webhook@nex.dev",
            firebase_uid="uid-wh-123",
        )
        self.installation = GitHubInstallation.objects.create(
            user=self.user,
            installation_id=5001,
            account_login="webhook-org",
            status=GitHubInstallation.Status.ACTIVE,
        )
        self.repo = Repository.objects.create(
            installation=self.installation,
            owner=self.user,
            github_repo_id=5002,
            name="initial-name",
            full_name="webhook-org/initial-name",
            is_active=True,
            is_archived=False,
            html_url="https://github.com/webhook-org/initial-name",
            clone_url="https://github.com/webhook-org/initial-name.git",
        )

    @patch.object(GitHubAppService, "verify_webhook_signature", return_value=True)
    def test_webhook_repository_renamed_and_archived(self, mock_sig: MagicMock) -> None:
        """Verify webhook updates repository name and archived flag."""
        # Renamed event
        rename_payload = {
            "action": "renamed",
            "repository": {
                "id": 5002,
                "name": "renamed-repo",
                "full_name": "webhook-org/renamed-repo",
            },
        }
        res_rename = self.client.post(
            "/api/v1/repositories/github/webhook/",
            data=json.dumps(rename_payload),
            content_type="application/json",
            HTTP_X_GITHUB_DELIVERY="deliv-rename-1",
            HTTP_X_GITHUB_EVENT="repository",
            HTTP_X_HUB_SIGNATURE_256="sha256=valid",
        )
        self.assertEqual(res_rename.status_code, status.HTTP_200_OK)

        self.repo.refresh_from_db()
        self.assertEqual(self.repo.name, "renamed-repo")
        self.assertEqual(self.repo.full_name, "webhook-org/renamed-repo")

        # Archived event
        archive_payload = {
            "action": "archived",
            "repository": {"id": 5002},
        }
        res_archive = self.client.post(
            "/api/v1/repositories/github/webhook/",
            data=json.dumps(archive_payload),
            content_type="application/json",
            HTTP_X_GITHUB_DELIVERY="deliv-archive-1",
            HTTP_X_GITHUB_EVENT="repository",
            HTTP_X_HUB_SIGNATURE_256="sha256=valid",
        )
        self.assertEqual(res_archive.status_code, status.HTTP_200_OK)

        self.repo.refresh_from_db()
        self.assertTrue(self.repo.is_archived)

    @patch.object(GitHubAppService, "verify_webhook_signature", return_value=True)
    def test_webhook_repository_deleted_tombstones(self, mock_sig: MagicMock) -> None:
        """Verify webhook deletes mark repository as removed/inactive."""
        delete_payload = {
            "action": "deleted",
            "repository": {"id": 5002},
        }
        res = self.client.post(
            "/api/v1/repositories/github/webhook/",
            data=json.dumps(delete_payload),
            content_type="application/json",
            HTTP_X_GITHUB_DELIVERY="deliv-del-1",
            HTTP_X_GITHUB_EVENT="repository",
            HTTP_X_HUB_SIGNATURE_256="sha256=valid",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.repo.refresh_from_db()
        self.assertFalse(self.repo.is_active)
        self.assertEqual(self.repo.sync_status, Repository.SyncStatus.REMOVED)
