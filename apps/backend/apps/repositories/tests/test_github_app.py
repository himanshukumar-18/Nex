"""Unit and integration test suite for GitHub App Authorization & Security (Phase 2).

Tests RS256 JWT generation, short-lived installation access token management,
Redis token caching, state generation and single-use consumption (anti-replay),
HMAC-SHA256 webhook signature validation, authenticated installation initiation,
callback verification, object-level cross-user isolation, and webhook lifecycle handling.
"""

import hashlib
import hmac
import json
import time
from typing import Any
from unittest.mock import MagicMock, patch

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit_logs.models import SecurityAuditEvent
from apps.repositories.models import GitHubInstallation, GitHubWebhookEvent
from apps.repositories.services.github_app import (
    GitHubAppAuthenticationError,
    GitHubAppConfigurationError,
    GitHubAppService,
    GitHubInstallationNotFoundError,
)


def generate_test_rsa_key_pair() -> tuple[str, str]:
    """Generate in-memory RSA key pair for cryptographic testing."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


TEST_PRIVATE_KEY, TEST_PUBLIC_KEY = generate_test_rsa_key_pair()


@override_settings(
    GITHUB_APP_ID="123456",
    GITHUB_APP_SLUG="nex-test-assistant",
    GITHUB_APP_PRIVATE_KEY=TEST_PRIVATE_KEY,
    GITHUB_WEBHOOK_SECRET="test-webhook-secret-98765",
)
class GitHubAppServiceTests(TestCase):
    """Unit tests for GitHubAppService cryptographic and token functions."""

    def setUp(self) -> None:
        cache.clear()

    def test_generate_app_jwt_valid(self) -> None:
        """Ensure App JWT is generated with RS256 and valid standard claims."""
        token = GitHubAppService.generate_app_jwt()
        assert isinstance(token, str)

        decoded = jwt.decode(
            token,
            TEST_PUBLIC_KEY,
            algorithms=["RS256"],
            options={"verify_exp": True},
        )
        assert decoded["iss"] == "123456"
        assert "iat" in decoded
        assert "exp" in decoded
        assert decoded["exp"] > decoded["iat"]

    @override_settings(GITHUB_APP_ID="", GITHUB_APP_PRIVATE_KEY="")
    def test_generate_app_jwt_unconfigured_raises_error(self) -> None:
        """Missing App ID or Private Key must raise GitHubAppConfigurationError."""
        with self.assertRaises(GitHubAppConfigurationError):
            GitHubAppService.generate_app_jwt()

    @patch("httpx.Client.post")
    def test_get_installation_access_token_and_cache(self, mock_post: MagicMock) -> None:
        """Token acquisition calls GitHub API and caches in Redis."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.is_error = False
        mock_response.json.return_value = {
            "token": "ghs_testToken12345",
            "expires_at": "2030-01-01T00:00:00Z",
        }
        mock_post.return_value = mock_response

        # 1. First call fetches from GitHub
        token1 = GitHubAppService.get_installation_access_token(999888)
        assert token1 == "ghs_testToken12345"
        assert mock_post.call_count == 1

        # 2. Second call must retrieve from Redis cache without calling GitHub
        token2 = GitHubAppService.get_installation_access_token(999888)
        assert token2 == "ghs_testToken12345"
        assert mock_post.call_count == 1

        # 3. Revoke cached token
        GitHubAppService.revoke_cached_token(999888)
        assert cache.get("github:token:999888") is None

    def test_state_generation_and_single_use_burn(self) -> None:
        """Verify state token generation and atomic single-use burn (replay defense)."""
        user_id = "user-uuid-1234"
        state = GitHubAppService.generate_authorization_state(user_id)
        assert len(state) >= 32

        # First consumption succeeds
        resolved_user_id = GitHubAppService.consume_authorization_state(state)
        assert resolved_user_id == user_id

        # Second consumption returns None (single-use burned)
        replay_attempt = GitHubAppService.consume_authorization_state(state)
        assert replay_attempt is None

    def test_webhook_signature_verification(self) -> None:
        """Verify HMAC-SHA256 signature verification."""
        payload = b'{"action":"created","installation":{"id":123}}'
        secret = "test-webhook-secret-98765"
        valid_sig = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

        # Valid signature
        assert GitHubAppService.verify_webhook_signature(payload, valid_sig) is True

        # Invalid signature
        assert GitHubAppService.verify_webhook_signature(payload, "sha256=invalidhash") is False

        # Malformed header
        assert GitHubAppService.verify_webhook_signature(payload, "md5=badprefix") is False

        # Missing header
        assert GitHubAppService.verify_webhook_signature(payload, None) is False

    def test_get_private_key_valid_inline_pem(self) -> None:
        """Valid inline PEM private key is loaded directly."""
        key = GitHubAppService.get_private_key()
        assert "BEGIN PRIVATE KEY" in key or "BEGIN RSA PRIVATE KEY" in key

    def test_get_private_key_valid_file_path(self) -> None:
        """When inline key is empty, key is loaded from GITHUB_APP_PRIVATE_KEY_PATH."""
        import tempfile
        with tempfile.NamedTemporaryFile("w+", delete=False) as f:
            f.write(TEST_PRIVATE_KEY)
            f.flush()
            tmp_path = f.name

        try:
            with override_settings(GITHUB_APP_PRIVATE_KEY="", GITHUB_APP_PRIVATE_KEY_PATH=tmp_path):
                key = GitHubAppService.get_private_key()
                assert key == TEST_PRIVATE_KEY.strip()
        finally:
            import os
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_get_private_key_fingerprint_fallback_to_file(self) -> None:
        """When GITHUB_APP_PRIVATE_KEY is a SHA256 fingerprint, it falls back to GITHUB_APP_PRIVATE_KEY_PATH."""
        import tempfile
        with tempfile.NamedTemporaryFile("w+", delete=False) as f:
            f.write(TEST_PRIVATE_KEY)
            f.flush()
            tmp_path = f.name

        fingerprint = "SHA256:0Fs0000000000000000000000000000000000000000="
        try:
            with override_settings(
                GITHUB_APP_PRIVATE_KEY=fingerprint,
                GITHUB_APP_PRIVATE_KEY_PATH=tmp_path,
            ):
                key = GitHubAppService.get_private_key()
                assert key == TEST_PRIVATE_KEY.strip()
        finally:
            import os
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_get_private_key_invalid_pem_raises_error(self) -> None:
        """Invalid inline PEM without a fallback file raises GitHubAppConfigurationError."""
        with override_settings(
            GITHUB_APP_PRIVATE_KEY="NOT_A_VALID_PEM_STRING",
            GITHUB_APP_PRIVATE_KEY_PATH="/nonexistent/path/key.pem",
        ):
            with self.assertRaises(GitHubAppConfigurationError):
                GitHubAppService.get_private_key()

    def test_is_configured_true_and_false(self) -> None:
        """is_configured returns True only when App ID and valid private key are present."""
        assert GitHubAppService.is_configured() is True

        with override_settings(GITHUB_APP_ID=""):
            assert GitHubAppService.is_configured() is False

        with override_settings(
            GITHUB_APP_ID="123456",
            GITHUB_APP_PRIVATE_KEY="INVALID_KEY",
            GITHUB_APP_PRIVATE_KEY_PATH="",
        ):
            assert GitHubAppService.is_configured() is False


@override_settings(
    GITHUB_APP_ID="123456",
    GITHUB_APP_SLUG="nex-test-assistant",
    GITHUB_APP_PRIVATE_KEY=TEST_PRIVATE_KEY,
    GITHUB_WEBHOOK_SECRET="test-webhook-secret-98765",
    GITHUB_APP_CALLBACK_URL="http://localhost:3000/settings",
)
class GitHubAuthorizationApiTests(TestCase):
    """Integration tests for GitHub App REST endpoints and webhook flows."""

    def setUp(self) -> None:
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="developer@nex.dev",
            firebase_uid="fb_dev_1001",
            role=User.Role.DEVELOPER,
        )
        self.other_user = User.objects.create_user(
            email="other@nex.dev",
            firebase_uid="fb_other_1002",
            role=User.Role.MEMBER,
        )

    def test_status_endpoint_unauthenticated(self) -> None:
        """Unauthenticated requests to status endpoint must return 401."""
        url = reverse("api_v1:repositories:github-status")
        response = self.client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_status_endpoint_authenticated(self) -> None:
        """Authenticated user receives configuration status and installations list."""
        self.client.force_authenticate(user=self.user)
        url = reverse("api_v1:repositories:github-status")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["configured"] is True
        assert data["app_slug"] == "nex-test-assistant"
        assert data["connected"] is False
        assert data["installations_count"] == 0

    def test_install_init_endpoint(self) -> None:
        """Initiate installation returns official install URL with signed state."""
        self.client.force_authenticate(user=self.user)
        url = reverse("api_v1:repositories:github-install-init")
        response = self.client.post(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "install_url" in data
        assert "state" in data
        assert "https://github.com/apps/nex-test-assistant/installations/new?state=" in data["install_url"]

        # Verify audit event was logged
        audit = SecurityAuditEvent.objects.filter(
            event_type=SecurityAuditEvent.EventType.GITHUB_INSTALLATION_INITIATED,
            user=self.user,
        ).first()
        assert audit is not None

    @patch("apps.repositories.services.github_app.GitHubAppService.get_installation")
    def test_callback_endpoint_valid_json(self, mock_get_inst: MagicMock) -> None:
        """Valid callback creates GitHubInstallation and links to authenticated user."""
        mock_get_inst.return_value = {
            "id": 554433,
            "account": {
                "login": "octocat-org",
                "type": "Organization",
                "avatar_url": "https://avatars.githubusercontent.com/u/9919",
            },
            "target_type": "selected",
            "permissions": {"metadata": "read", "contents": "read"},
        }

        # Generate state bound to self.user
        state = GitHubAppService.generate_authorization_state(str(self.user.id))

        url = reverse("api_v1:repositories:github-install-callback")
        response = self.client.get(
            url,
            {"installation_id": "554433", "state": state, "setup_action": "install"},
            HTTP_ACCEPT="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "connected"
        assert data["installation"]["installation_id"] == 554433
        assert data["installation"]["account_login"] == "octocat-org"

        # Verify DB record exists and belongs to self.user
        inst = GitHubInstallation.objects.get(installation_id=554433)
        assert inst.user == self.user
        assert inst.account_login == "octocat-org"
        assert inst.status == GitHubInstallation.Status.ACTIVE

    def test_callback_endpoint_invalid_state(self) -> None:
        """Callback with an invalid or expired state token must return 400."""
        url = reverse("api_v1:repositories:github-install-callback")
        response = self.client.get(
            url,
            {"installation_id": "554433", "state": "invalid-state-token"},
            HTTP_ACCEPT="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["error"] == "INVALID_STATE"

    @patch("apps.repositories.services.github_app.GitHubAppService.get_installation")
    def test_callback_duplicate_idempotent(self, mock_get_inst: MagicMock) -> None:
        """Duplicate callbacks update metadata without raising integrity errors."""
        mock_get_inst.return_value = {
            "id": 554433,
            "account": {"login": "octocat-org", "type": "Organization"},
            "target_type": "all",
            "permissions": {"metadata": "read"},
        }

        # Pre-existing installation
        GitHubInstallation.objects.create(
            user=self.user,
            installation_id=554433,
            account_login="octocat-org",
            account_type="Organization",
            status=GitHubInstallation.Status.SUSPENDED,
        )

        state = GitHubAppService.generate_authorization_state(str(self.user.id))
        url = reverse("api_v1:repositories:github-install-callback")
        response = self.client.get(
            url,
            {"installation_id": "554433", "state": state},
            HTTP_ACCEPT="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        inst = GitHubInstallation.objects.get(installation_id=554433)
        assert inst.status == GitHubInstallation.Status.ACTIVE
        assert inst.target_type == "all"

    @patch("apps.repositories.services.sync.RepositorySyncService.sync_installation_repositories")
    @patch("apps.repositories.services.github_app.GitHubAppService.get_installation")
    def test_callback_html_redirect_fresh_install(
        self,
        mock_get_inst: MagicMock,
        mock_sync: MagicMock,
    ) -> None:
        """Browser callback with HTML accept header redirects to frontend settings with connected status."""
        mock_get_inst.return_value = {
            "id": 554433,
            "account": {"login": "octocat-org", "type": "Organization"},
            "target_type": "selected",
            "permissions": {"metadata": "read"},
        }

        state = GitHubAppService.generate_authorization_state(str(self.user.id))
        url = reverse("api_v1:repositories:github-install-callback")
        response = self.client.get(
            url,
            {"installation_id": "554433", "state": state, "setup_action": "install"},
            HTTP_ACCEPT="text/html,application/xhtml+xml",
        )

        assert response.status_code == status.HTTP_302_FOUND
        assert response["Location"] == "http://localhost:3000/settings?github=connected&installation_id=554433"

    def test_callback_missing_installation_id(self) -> None:
        """Callback missing installation_id returns 400 for JSON and 302 for HTML."""
        url = reverse("api_v1:repositories:github-install-callback")
        json_res = self.client.get(url, HTTP_ACCEPT="application/json")
        assert json_res.status_code == status.HTTP_400_BAD_REQUEST
        assert json_res.json()["error"] == "MISSING_PARAMETERS"

        html_res = self.client.get(url, HTTP_ACCEPT="text/html")
        assert html_res.status_code == status.HTTP_302_FOUND
        assert "github=error&error=MISSING_INSTALLATION_ID" in html_res["Location"]

    def test_callback_invalid_installation_id(self) -> None:
        """Callback with non-numeric installation_id returns 400 for JSON and 302 for HTML."""
        url = reverse("api_v1:repositories:github-install-callback")
        json_res = self.client.get(url, {"installation_id": "invalid-id"}, HTTP_ACCEPT="application/json")
        assert json_res.status_code == status.HTTP_400_BAD_REQUEST
        assert json_res.json()["error"] == "INVALID_INSTALLATION_ID"

        html_res = self.client.get(url, {"installation_id": "invalid-id"}, HTTP_ACCEPT="text/html")
        assert html_res.status_code == status.HTTP_302_FOUND
        assert "github=error&error=INVALID_INSTALLATION_ID" in html_res["Location"]

    @patch("apps.repositories.services.github_app.GitHubAppService.get_installation")
    def test_callback_state_replay_rejected(self, mock_get_inst: MagicMock) -> None:
        """Consuming a state token a second time is rejected with INVALID_STATE."""
        mock_get_inst.return_value = {
            "id": 554433,
            "account": {"login": "octocat-org", "type": "Organization"},
            "target_type": "selected",
            "permissions": {"metadata": "read"},
        }
        state = GitHubAppService.generate_authorization_state(str(self.user.id))
        url = reverse("api_v1:repositories:github-install-callback")

        # 1. First consumption succeeds
        res1 = self.client.get(
            url,
            {"installation_id": "554433", "state": state},
            HTTP_ACCEPT="application/json",
        )
        assert res1.status_code == status.HTTP_200_OK

        # 2. Second consumption fails (token burned)
        res2 = self.client.get(
            url,
            {"installation_id": "554433", "state": state},
            HTTP_ACCEPT="application/json",
        )
        assert res2.status_code == status.HTTP_400_BAD_REQUEST
        assert res2.json()["error"] == "INVALID_STATE"

    @patch("apps.repositories.services.sync.RepositorySyncService.sync_installation_repositories")
    @patch("apps.repositories.services.github_app.GitHubAppService.get_installation")
    def test_callback_existing_installation_without_state_succeeds(
        self,
        mock_get_inst: MagicMock,
        mock_sync: MagicMock,
    ) -> None:
        """Setup URL callback without state for an existing verified installation updates metadata."""
        mock_get_inst.return_value = {
            "id": 554433,
            "account": {"login": "octocat-org", "type": "Organization"},
            "target_type": "all",
            "permissions": {"metadata": "read", "contents": "write"},
        }

        # Pre-existing installation bound to user
        GitHubInstallation.objects.create(
            user=self.user,
            installation_id=554433,
            account_login="octocat-org",
            account_type="Organization",
            status=GitHubInstallation.Status.ACTIVE,
        )

        url = reverse("api_v1:repositories:github-install-callback")
        response = self.client.get(
            url,
            {"installation_id": "554433", "setup_action": "update"},
            HTTP_ACCEPT="text/html",
        )

        assert response.status_code == status.HTTP_302_FOUND
        assert response["Location"] == "http://localhost:3000/settings?github=updated&installation_id=554433"

        inst = GitHubInstallation.objects.get(installation_id=554433)
        assert inst.permissions == {"metadata": "read", "contents": "write"}

    def test_callback_unbound_installation_without_state_rejected(self) -> None:
        """Setup URL callback without state for an unbound installation is rejected (never bound unsafely)."""
        url = reverse("api_v1:repositories:github-install-callback")
        json_res = self.client.get(
            url,
            {"installation_id": "999888", "setup_action": "install"},
            HTTP_ACCEPT="application/json",
        )
        assert json_res.status_code == status.HTTP_400_BAD_REQUEST
        assert json_res.json()["error"] == "UNVERIFIED_INSTALLATION"

        html_res = self.client.get(
            url,
            {"installation_id": "999888", "setup_action": "install"},
            HTTP_ACCEPT="text/html",
        )
        assert html_res.status_code == status.HTTP_302_FOUND
        assert "github=error&error=UNVERIFIED_INSTALLATION" in html_res["Location"]

    @patch("apps.repositories.services.sync.RepositorySyncService.sync_installation_repositories")
    @patch("apps.repositories.services.github_app.GitHubAppService.get_installation")
    def test_callback_initial_sync_failure_non_fatal(
        self,
        mock_get_inst: MagicMock,
        mock_sync: MagicMock,
    ) -> None:
        """Initial repository sync errors do not block callback completion or 302 redirect."""
        mock_get_inst.return_value = {
            "id": 554433,
            "account": {"login": "octocat-org", "type": "Organization"},
            "target_type": "selected",
            "permissions": {"metadata": "read"},
        }
        mock_sync.side_effect = RuntimeError("Sync network timeout")

        state = GitHubAppService.generate_authorization_state(str(self.user.id))
        url = reverse("api_v1:repositories:github-install-callback")
        response = self.client.get(
            url,
            {"installation_id": "554433", "state": state},
            HTTP_ACCEPT="text/html",
        )

        # Still redirects successfully to connected page with sync=failed flag despite sync failure
        assert response.status_code == status.HTTP_302_FOUND
        assert response["Location"] == "http://localhost:3000/settings?github=connected&installation_id=554433&sync=failed"
        inst = GitHubInstallation.objects.get(installation_id=554433)
        assert inst.status == GitHubInstallation.Status.ACTIVE

    def test_insecure_link_endpoint_not_available(self) -> None:
        """Insecure linking without authorization flow is strictly prohibited (404 Not Found)."""
        self.client.force_authenticate(user=self.user)
        response = self.client.post("/api/v1/repositories/github/installations/link/", {"installation_id": 178260462})
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_installation_disconnect(self) -> None:
        """Owner can disconnect installation; status is marked DELETED."""
        inst = GitHubInstallation.objects.create(
            user=self.user,
            installation_id=887766,
            account_login="octocat",
            status=GitHubInstallation.Status.ACTIVE,
        )

        self.client.force_authenticate(user=self.user)
        url = reverse(
            "api_v1:repositories:github-installation-disconnect",
            kwargs={"installation_id": 887766},
        )
        response = self.client.post(url)
        assert response.status_code == status.HTTP_200_OK

        inst.refresh_from_db()
        assert inst.status == GitHubInstallation.Status.DELETED

    def test_installation_disconnect_cross_user_denied(self) -> None:
        """Attempting to disconnect another user's installation returns 404."""
        inst = GitHubInstallation.objects.create(
            user=self.user,
            installation_id=887766,
            account_login="octocat",
            status=GitHubInstallation.Status.ACTIVE,
        )

        # Authenticate as other_user
        self.client.force_authenticate(user=self.other_user)
        url = reverse(
            "api_v1:repositories:github-installation-disconnect",
            kwargs={"installation_id": 887766},
        )
        response = self.client.post(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

        inst.refresh_from_db()
        assert inst.status == GitHubInstallation.Status.ACTIVE

    def test_webhook_invalid_signature_rejected(self) -> None:
        """Webhook with invalid signature header returns 401."""
        url = reverse("api_v1:repositories:github-webhook")
        body = json.dumps({"action": "deleted"}).encode("utf-8")
        response = self.client.post(
            url,
            data=body,
            content_type="application/json",
            HTTP_X_GITHUB_DELIVERY="deliv-1234",
            HTTP_X_GITHUB_EVENT="installation",
            HTTP_X_HUB_SIGNATURE_256="sha256=invalidhash",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_webhook_installation_deleted_lifecycle(self) -> None:
        """Verified webhook for installation.deleted marks installation DELETED."""
        inst = GitHubInstallation.objects.create(
            user=self.user,
            installation_id=112233,
            account_login="org-test",
            status=GitHubInstallation.Status.ACTIVE,
        )

        payload_dict = {
            "action": "deleted",
            "installation": {"id": 112233},
        }
        raw_body = json.dumps(payload_dict).encode("utf-8")
        secret = "test-webhook-secret-98765"
        sig = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()

        url = reverse("api_v1:repositories:github-webhook")
        response = self.client.post(
            url,
            data=raw_body,
            content_type="application/json",
            HTTP_X_GITHUB_DELIVERY="deliv-unique-001",
            HTTP_X_GITHUB_EVENT="installation",
            HTTP_X_HUB_SIGNATURE_256=sig,
        )

        assert response.status_code == status.HTTP_200_OK
        inst.refresh_from_db()
        assert inst.status == GitHubInstallation.Status.DELETED

    def test_webhook_duplicate_delivery_deduplication(self) -> None:
        """Duplicate webhook delivery ID returns already_processed without re-execution."""
        payload_dict = {
            "action": "created",
            "installation": {"id": 112233},
        }
        raw_body = json.dumps(payload_dict).encode("utf-8")
        secret = "test-webhook-secret-98765"
        sig = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()

        url = reverse("api_v1:repositories:github-webhook")

        # Delivery 1
        res1 = self.client.post(
            url,
            data=raw_body,
            content_type="application/json",
            HTTP_X_GITHUB_DELIVERY="deliv-dup-999",
            HTTP_X_GITHUB_EVENT="installation",
            HTTP_X_HUB_SIGNATURE_256=sig,
        )
        assert res1.status_code == status.HTTP_200_OK
        assert res1.json()["status"] == "processed"

        # Delivery 2 with same delivery_id
        res2 = self.client.post(
            url,
            data=raw_body,
            content_type="application/json",
            HTTP_X_GITHUB_DELIVERY="deliv-dup-999",
            HTTP_X_GITHUB_EVENT="installation",
            HTTP_X_HUB_SIGNATURE_256=sig,
        )
        assert res2.status_code == status.HTTP_200_OK
        assert res2.json()["status"] == "already_processed"

    def test_webhook_installation_suspend_and_unsuspend(self) -> None:
        """Verified webhook handles suspend and unsuspend actions."""
        inst = GitHubInstallation.objects.create(
            user=self.user,
            installation_id=334455,
            account_login="org-suspend-test",
            status=GitHubInstallation.Status.ACTIVE,
        )

        secret = "test-webhook-secret-98765"
        url = reverse("api_v1:repositories:github-webhook")

        # 1. Suspend
        raw_body1 = json.dumps({"action": "suspend", "installation": {"id": 334455}}).encode("utf-8")
        sig1 = "sha256=" + hmac.new(secret.encode(), raw_body1, hashlib.sha256).hexdigest()
        res1 = self.client.post(
            url,
            data=raw_body1,
            content_type="application/json",
            HTTP_X_GITHUB_DELIVERY="deliv-suspend-01",
            HTTP_X_GITHUB_EVENT="installation",
            HTTP_X_HUB_SIGNATURE_256=sig1,
        )
        assert res1.status_code == status.HTTP_200_OK
        inst.refresh_from_db()
        assert inst.status == GitHubInstallation.Status.SUSPENDED

        # 2. Unsuspend
        raw_body2 = json.dumps({"action": "unsuspend", "installation": {"id": 334455}}).encode("utf-8")
        sig2 = "sha256=" + hmac.new(secret.encode(), raw_body2, hashlib.sha256).hexdigest()
        res2 = self.client.post(
            url,
            data=raw_body2,
            content_type="application/json",
            HTTP_X_GITHUB_DELIVERY="deliv-unsuspend-02",
            HTTP_X_GITHUB_EVENT="installation",
            HTTP_X_HUB_SIGNATURE_256=sig2,
        )
        assert res2.status_code == status.HTTP_200_OK
        inst.refresh_from_db()
        assert inst.status == GitHubInstallation.Status.ACTIVE

    def test_webhook_unsupported_event_is_handled_cleanly(self) -> None:
        """Unsupported webhook events are recorded and return 200 without error."""
        secret = "test-webhook-secret-98765"
        url = reverse("api_v1:repositories:github-webhook")
        raw_body = json.dumps({"action": "started"}).encode("utf-8")
        sig = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()

        response = self.client.post(
            url,
            data=raw_body,
            content_type="application/json",
            HTTP_X_GITHUB_DELIVERY="deliv-unsupported-01",
            HTTP_X_GITHUB_EVENT="workflow_run",
            HTTP_X_HUB_SIGNATURE_256=sig,
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "processed"
