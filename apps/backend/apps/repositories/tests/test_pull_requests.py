"""NEX Repositories — GitHub Pull Request Integration Tests (Phase 5).

Verifies Pull Request preview generation, cryptographic fingerprint binding,
PR publishing via GitHub App, idempotency, object-level tenant isolation,
live PR status synchronization, and webhook lifecycle handling.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone as django_timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit_logs.models import SecurityAuditEvent
from apps.repositories.models import (
    GitHubInstallation,
    GitHubWebhookEvent,
    PullRequest,
    Repository,
)
from apps.repositories.services.github_app import GitHubAppService


class PullRequestIntegrationTestCase(TestCase):
    """Test suite for Pull Request preview, creation, sync, and webhook lifecycle."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="developer@nex.dev",
            firebase_uid="uid-dev-pr-101",
        )
        self.intruder = User.objects.create_user(
            email="intruder@nex.dev",
            firebase_uid="uid-intruder-pr-202",
        )

        self.installation = GitHubInstallation.objects.create(
            user=self.user,
            installation_id=998877,
            account_login="nex-org",
            status=GitHubInstallation.Status.ACTIVE,
        )

        self.repo = Repository.objects.create(
            installation=self.installation,
            owner=self.user,
            github_repo_id=778899,
            name="awesome-app",
            full_name="nex-org/awesome-app",
            default_branch="main",
            is_active=True,
            is_archived=False,
            html_url="https://github.com/nex-org/awesome-app",
            clone_url="https://github.com/nex-org/awesome-app.git",
        )

    @patch("apps.repositories.services.github_app.GitHubAppService.get_installation_access_token")
    @patch("httpx.Client.get")
    def test_preview_pull_request_success(self, mock_get: MagicMock, mock_token: MagicMock) -> None:
        """Verify previewing changes between base and head branches generates bound fingerprint."""
        self.client.force_authenticate(user=self.user)
        mock_token.return_value = "ghs_mock_preview_token"

        mock_compare_response = MagicMock()
        mock_compare_response.status_code = 200
        mock_compare_response.is_error = False
        mock_compare_response.json.return_value = {
            "status": "ahead",
            "ahead_by": 2,
            "behind_by": 0,
            "total_commits": 2,
            "base_commit": {"sha": "base111111"},
            "commits": [
                {
                    "sha": "c111111111111111111111111111111111111111",
                    "commit": {
                        "message": "Add user authentication\nDetailed commit message body",
                        "author": {"name": "Developer", "date": "2026-11-03T10:00:00Z"},
                    },
                },
                {
                    "sha": "c222222222222222222222222222222222222222",
                    "commit": {
                        "message": "Add password hashing",
                        "author": {"name": "Developer", "date": "2026-11-03T11:00:00Z"},
                    },
                },
            ],
            "files": [
                {
                    "filename": "auth.py",
                    "status": "added",
                    "additions": 45,
                    "deletions": 0,
                    "changes": 45,
                }
            ],
        }
        mock_get.return_value = mock_compare_response

        url = f"/api/v1/repositories/{self.repo.id}/pulls/preview/"
        res = self.client.post(url, {"head": "feature/auth", "base": "main"}, format="json")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(data["base"], "main")
        self.assertEqual(data["head"], "feature/auth")
        self.assertEqual(data["ahead_by"], 2)
        self.assertEqual(data["total_commits"], 2)
        self.assertEqual(data["total_files"], 1)
        self.assertTrue(len(data["preview_fingerprint"]) > 16)
        self.assertEqual(data["commits"][0]["message"], "Add user authentication")

    def test_preview_identical_branches_rejected(self) -> None:
        """Verify previewing changes where head == base raises 400 validation error."""
        self.client.force_authenticate(user=self.user)
        url = f"/api/v1/repositories/{self.repo.id}/pulls/preview/"
        res = self.client.post(url, {"head": "main", "base": "main"}, format="json")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("apps.repositories.services.github_app.GitHubAppService.get_installation_access_token")
    @patch("httpx.Client.get")
    def test_preview_remote_branch_missing(self, mock_get: MagicMock, mock_token: MagicMock) -> None:
        """Verify 400 error when GitHub returns 404 for compare."""
        self.client.force_authenticate(user=self.user)
        mock_token.return_value = "ghs_mock_token"

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.is_error = True
        mock_get.return_value = mock_resp

        url = f"/api/v1/repositories/{self.repo.id}/pulls/preview/"
        res = self.client.post(url, {"head": "nonexistent", "base": "main"}, format="json")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("apps.repositories.services.github_app.GitHubAppService.get_installation_access_token")
    @patch("httpx.Client.get")
    @patch("httpx.Client.post")
    def test_create_pull_request_success(
        self, mock_post: MagicMock, mock_get: MagicMock, mock_token: MagicMock
    ) -> None:
        """Verify publishing an approved PR after preview binds fingerprint and logs audit event."""
        self.client.force_authenticate(user=self.user)
        mock_token.return_value = "ghs_mock_token"

        # 1. Preview changes first to obtain fingerprint
        mock_compare_resp = MagicMock()
        mock_compare_resp.status_code = 200
        mock_compare_resp.is_error = False
        mock_compare_resp.json.return_value = {
            "status": "ahead",
            "ahead_by": 1,
            "behind_by": 0,
            "total_commits": 1,
            "base_commit": {"sha": "base111"},
            "commits": [{"sha": "sha111", "commit": {"message": "Initial feature", "author": {}}}],
            "files": [{"filename": "main.py", "status": "modified", "additions": 10, "deletions": 2}],
        }
        mock_get.return_value = mock_compare_resp

        preview_res = self.client.post(
            f"/api/v1/repositories/{self.repo.id}/pulls/preview/",
            {"head": "feature/login", "base": "main"},
            format="json",
        )
        self.assertEqual(preview_res.status_code, status.HTTP_200_OK)
        fingerprint = preview_res.json()["preview_fingerprint"]

        # 2. Publish PR
        mock_pr_create_resp = MagicMock()
        mock_pr_create_resp.status_code = 201
        mock_pr_create_resp.is_error = False
        mock_pr_create_resp.json.return_value = {
            "id": 88112233,
            "number": 14,
            "title": "Add Login Support",
            "body": "Implements login via PKCE",
            "state": "open",
            "draft": False,
            "merged": False,
            "html_url": "https://github.com/nex-org/awesome-app/pull/14",
            "base": {"ref": "main"},
            "head": {"ref": "feature/login"},
            "comments": 0,
            "commits": 1,
            "additions": 10,
            "deletions": 2,
            "changed_files": 1,
        }
        mock_post.return_value = mock_pr_create_resp

        create_url = f"/api/v1/repositories/{self.repo.id}/pulls/"
        create_res = self.client.post(
            create_url,
            {
                "title": "Add Login Support",
                "head": "feature/login",
                "base": "main",
                "body": "Implements login via PKCE",
                "draft": False,
                "preview_fingerprint": fingerprint,
                "approved": True,
            },
            format="json",
        )

        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        pr_data = create_res.json()
        self.assertEqual(pr_data["number"], 14)
        self.assertEqual(pr_data["state"], "open")
        self.assertEqual(pr_data["head_branch"], "feature/login")
        self.assertEqual(pr_data["base_branch"], "main")

        # Verify DB persistence
        pr_record = PullRequest.objects.get(github_pr_id=88112233)
        self.assertEqual(pr_record.number, 14)
        self.assertEqual(pr_record.repository, self.repo)
        self.assertEqual(pr_record.user, self.user)

        # Verify SecurityAuditEvent was logged
        audit = SecurityAuditEvent.objects.filter(
            event_type=SecurityAuditEvent.EventType.GITHUB_PULL_REQUEST_CREATED
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.metadata.get("pr_number"), 14)

    def test_create_pull_request_without_approval_rejected(self) -> None:
        """Verify creating a PR without approved=True raises 400 validation error."""
        self.client.force_authenticate(user=self.user)
        create_url = f"/api/v1/repositories/{self.repo.id}/pulls/"
        res = self.client.post(
            create_url,
            {
                "title": "Unapproved PR",
                "head": "feature/test",
                "base": "main",
                "approved": False,
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_pull_request_invalid_fingerprint_rejected(self) -> None:
        """Verify submitting an expired or forged fingerprint raises 400 validation error."""
        self.client.force_authenticate(user=self.user)
        create_url = f"/api/v1/repositories/{self.repo.id}/pulls/"
        res = self.client.post(
            create_url,
            {
                "title": "Forged Fingerprint PR",
                "head": "feature/test",
                "base": "main",
                "preview_fingerprint": "manipulated_invalid_hash_123456",
                "approved": True,
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cross_user_isolation(self) -> None:
        """Verify that intruder user cannot preview or create PR on another user's repository."""
        self.client.force_authenticate(user=self.intruder)

        # Preview
        res_preview = self.client.post(
            f"/api/v1/repositories/{self.repo.id}/pulls/preview/",
            {"head": "feature/hack", "base": "main"},
            format="json",
        )
        self.assertEqual(res_preview.status_code, status.HTTP_404_NOT_FOUND)

        # Create
        res_create = self.client.post(
            f"/api/v1/repositories/{self.repo.id}/pulls/",
            {"title": "Intrusion PR", "head": "hack", "base": "main", "approved": True},
            format="json",
        )
        self.assertEqual(res_create.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_and_filter_pull_requests(self) -> None:
        """Verify listing PRs and filtering by state."""
        self.client.force_authenticate(user=self.user)

        PullRequest.objects.create(
            user=self.user,
            repository=self.repo,
            installation=self.installation,
            github_pr_id=101,
            number=1,
            title="Open PR",
            base_branch="main",
            head_branch="feature/1",
            html_url="https://github.com/nex-org/awesome-app/pull/1",
            state=PullRequest.State.OPEN,
        )
        PullRequest.objects.create(
            user=self.user,
            repository=self.repo,
            installation=self.installation,
            github_pr_id=102,
            number=2,
            title="Merged PR",
            base_branch="main",
            head_branch="feature/2",
            html_url="https://github.com/nex-org/awesome-app/pull/2",
            state=PullRequest.State.MERGED,
        )

        # 1. List all
        res_all = self.client.get(f"/api/v1/repositories/{self.repo.id}/pulls/")
        self.assertEqual(res_all.status_code, status.HTTP_200_OK)
        self.assertEqual(res_all.json()["count"], 2)

        # 2. Filter open
        res_open = self.client.get(f"/api/v1/repositories/{self.repo.id}/pulls/?state=open")
        self.assertEqual(res_open.status_code, status.HTTP_200_OK)
        self.assertEqual(res_open.json()["count"], 1)
        self.assertEqual(res_open.json()["results"][0]["title"], "Open PR")

    @patch("apps.repositories.services.github_app.GitHubAppService.get_installation_access_token")
    @patch("httpx.Client.get")
    def test_get_and_sync_pull_request(self, mock_get: MagicMock, mock_token: MagicMock) -> None:
        """Verify retrieving details and manually syncing live PR state."""
        self.client.force_authenticate(user=self.user)
        mock_token.return_value = "ghs_mock_token"

        pr = PullRequest.objects.create(
            user=self.user,
            repository=self.repo,
            installation=self.installation,
            github_pr_id=202,
            number=5,
            title="Original PR",
            base_branch="main",
            head_branch="feature/sync",
            html_url="https://github.com/nex-org/awesome-app/pull/5",
            state=PullRequest.State.OPEN,
        )

        # Detail query
        res_detail = self.client.get(f"/api/v1/repositories/{self.repo.id}/pulls/5/")
        self.assertEqual(res_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(res_detail.json()["number"], 5)

        # Live sync (simulating PR was merged on GitHub)
        mock_gh_resp = MagicMock()
        mock_gh_resp.status_code = 200
        mock_gh_resp.is_error = False
        mock_gh_resp.json.return_value = {
            "id": 202,
            "number": 5,
            "title": "Original PR",
            "body": "Updated description",
            "state": "closed",
            "merged": True,
            "html_url": "https://github.com/nex-org/awesome-app/pull/5",
            "base": {"ref": "main"},
            "head": {"ref": "feature/sync"},
        }
        mock_get.return_value = mock_gh_resp

        res_sync = self.client.post(f"/api/v1/repositories/{self.repo.id}/pulls/5/sync/")
        self.assertEqual(res_sync.status_code, status.HTTP_200_OK)
        self.assertEqual(res_sync.json()["state"], "merged")

        # Verify DB updated
        pr.refresh_from_db()
        self.assertEqual(pr.state, PullRequest.State.MERGED)

    @patch("apps.repositories.services.github_app.GitHubAppService.verify_webhook_signature", return_value=True)
    def test_webhook_pull_request_lifecycle(self, _mock_sig: MagicMock) -> None:
        """Verify webhook ingest updates PullRequest record for opened, closed, and merged actions."""
        # 1. PR Opened webhook
        payload_opened = {
            "action": "opened",
            "repository": {"id": self.repo.github_repo_id},
            "pull_request": {
                "id": 999111,
                "number": 42,
                "title": "Webhook Generated PR",
                "body": "Testing webhooks",
                "state": "open",
                "merged": False,
                "html_url": "https://github.com/nex-org/awesome-app/pull/42",
                "base": {"ref": "main"},
                "head": {"ref": "feature/webhook"},
            },
        }

        res_opened = self.client.post(
            "/api/v1/repositories/github/webhook/",
            data=json.dumps(payload_opened),
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="pull_request",
            HTTP_X_GITHUB_DELIVERY="deliv-pr-001",
            HTTP_X_HUB_SIGNATURE_256="sha256=mock",
        )
        self.assertEqual(res_opened.status_code, status.HTTP_200_OK)

        pr_record = PullRequest.objects.get(github_pr_id=999111)
        self.assertEqual(pr_record.number, 42)
        self.assertEqual(pr_record.state, PullRequest.State.OPEN)

        # 2. PR Merged webhook
        payload_merged = {
            "action": "closed",
            "repository": {"id": self.repo.github_repo_id},
            "pull_request": {
                "id": 999111,
                "number": 42,
                "title": "Webhook Generated PR",
                "state": "closed",
                "merged": True,
                "html_url": "https://github.com/nex-org/awesome-app/pull/42",
                "base": {"ref": "main"},
                "head": {"ref": "feature/webhook"},
            },
        }

        res_merged = self.client.post(
            "/api/v1/repositories/github/webhook/",
            data=json.dumps(payload_merged),
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="pull_request",
            HTTP_X_GITHUB_DELIVERY="deliv-pr-002",
            HTTP_X_HUB_SIGNATURE_256="sha256=mock",
        )
        self.assertEqual(res_merged.status_code, status.HTTP_200_OK)

        pr_record.refresh_from_db()
        self.assertEqual(pr_record.state, PullRequest.State.MERGED)
