"""NEX Repositories — Git Operations & Push Token Tests.

Verifies GitOperation model persistence, tenant isolation, operation history
querying, and short-lived push token minting with GitHub App integration.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone as django_timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit_logs.models import SecurityAuditEvent
from apps.repositories.models import GitHubInstallation, GitOperation, Repository
from apps.repositories.services.github_app import GitHubAppService


class GitOperationTestCase(TestCase):
    """Test suite for GitOperation tracking and push token generation."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="dev-ops@nex.dev",
            firebase_uid="uid-dev-ops-101",
        )
        self.other_user = User.objects.create_user(
            email="intruder@nex.dev",
            firebase_uid="uid-intruder-202",
        )

        self.installation = GitHubInstallation.objects.create(
            user=self.user,
            installation_id=112233,
            account_login="nex-corp",
            status=GitHubInstallation.Status.ACTIVE,
        )

        self.repo = Repository.objects.create(
            installation=self.installation,
            owner=self.user,
            github_repo_id=99001,
            name="core-service",
            full_name="nex-corp/core-service",
            is_active=True,
            is_archived=False,
            html_url="https://github.com/nex-corp/core-service",
            clone_url="https://github.com/nex-corp/core-service.git",
        )

    def test_record_and_list_git_operations(self) -> None:
        """Verify recording a Git operation from CLI and querying history."""
        self.client.force_authenticate(user=self.user)

        # 1. Record an operation
        payload = {
            "repository_id": str(self.repo.id),
            "operation_type": "commit",
            "target_branch": "feature/auth",
            "commit_sha": "a1b2c3d4e5f6",
            "commit_message": "feat: add oauth verification",
            "status": "executed",
            "risk_level": "high",
            "approval_status": "approved",
            "files": ["auth.py", "middleware.py"],
        }
        res_create = self.client.post("/api/v1/repositories/operations/", data=payload, format="json")
        self.assertEqual(res_create.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_create.json()["commit_sha"], "a1b2c3d4e5f6")

        # 2. Query repository-scoped operations
        res_list = self.client.get(f"/api/v1/repositories/{self.repo.id}/operations/")
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        data = res_list.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["operation_type"], "commit")
        self.assertEqual(data["results"][0]["target_branch"], "feature/auth")

    def test_operation_tenant_isolation(self) -> None:
        """Verify cross-tenant isolation: User B cannot access User A's operations."""
        op = GitOperation.objects.create(
            user=self.user,
            repository=self.repo,
            operation_type=GitOperation.OperationType.PUSH,
            target_branch="main",
            status=GitOperation.Status.EXECUTED,
            risk_level=GitOperation.RiskLevel.CRITICAL,
            approval_status=GitOperation.ApprovalStatus.APPROVED,
        )

        self.client.force_authenticate(user=self.other_user)

        # Other user querying own operations sees empty list
        res_empty = self.client.get("/api/v1/repositories/operations/")
        self.assertEqual(res_empty.status_code, status.HTTP_200_OK)
        self.assertEqual(res_empty.json()["count"], 0)

        # Other user trying to query User A's repository operations gets 404
        res_404 = self.client.get(f"/api/v1/repositories/{self.repo.id}/operations/")
        self.assertEqual(res_404.status_code, status.HTTP_404_NOT_FOUND)

    @patch.object(GitHubAppService, "get_installation_access_token", return_value="ghs_push_token_98765")
    def test_mint_push_token_success(self, mock_get_token: MagicMock) -> None:
        """Verify minting a short-lived push token for an authorized repository."""
        self.client.force_authenticate(user=self.user)
        response = self.client.post(f"/api/v1/repositories/{self.repo.id}/push-token/", data={}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["token"], "ghs_push_token_98765")
        self.assertEqual(data["repository"], "nex-corp/core-service")
        self.assertIn("expires_at", data)
        mock_get_token.assert_called_once()

        # Verify audit log was recorded
        audit = SecurityAuditEvent.objects.filter(
            user=self.user,
            event_type=SecurityAuditEvent.EventType.GITHUB_TOKEN_GENERATED,
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.metadata.get("repository"), "nex-corp/core-service")

    def test_push_token_inactive_installation_fails(self) -> None:
        """Verify push token generation is blocked if GitHub installation is suspended."""
        self.installation.status = GitHubInstallation.Status.SUSPENDED
        self.installation.save()

        self.client.force_authenticate(user=self.user)
        response = self.client.post(f"/api/v1/repositories/{self.repo.id}/push-token/", data={}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["error"], "INSTALLATION_INACTIVE")

    def test_push_token_cross_tenant_forbidden(self) -> None:
        """Verify cross-tenant isolation: User B cannot request push token for User A's repo."""
        self.client.force_authenticate(user=self.other_user)
        response = self.client.post(f"/api/v1/repositories/{self.repo.id}/push-token/", data={}, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

