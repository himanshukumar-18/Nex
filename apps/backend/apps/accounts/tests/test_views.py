"""
NEX Accounts — Tests for Profile, Session Management, Logout Views and Permissions.
"""

import hashlib
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import CliSession, User
from apps.accounts.permissions import IsAdminRole, IsDeveloperOrAdmin, IsEmailVerified


class AccountsViewsTests(TestCase):
    """Test suite for identity and session management views."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = User.objects.create(
            firebase_uid="fb_view_user",
            email="developer@nex.dev",
            email_verified=True,
            display_name="Dev User",
            role=User.Role.DEVELOPER,
            is_active=True,
        )
        self.client.force_authenticate(user=self.user)

    def test_me_view_returns_authenticated_user_profile(self) -> None:
        url = reverse("api_v1:accounts:me")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["email"], "developer@nex.dev")
        self.assertEqual(data["display_name"], "Dev User")
        self.assertEqual(data["role"], "developer")
        self.assertTrue(data["email_verified"])

    def test_unauthenticated_request_to_me_view_fails(self) -> None:
        unauth_client = APIClient()
        url = reverse("api_v1:accounts:me")
        response = unauth_client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_sync_profile_view_updates_display_name_and_avatar(self) -> None:
        url = reverse("api_v1:accounts:sync")
        payload = {
            "display_name": "Updated Dev Name",
            "avatar_url": "https://nex.dev/new_avatar.jpg",
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["display_name"], "Updated Dev Name")
        self.assertEqual(data["avatar_url"], "https://nex.dev/new_avatar.jpg")

        self.user.refresh_from_db()
        self.assertEqual(self.user.display_name, "Updated Dev Name")

    def test_cli_sessions_list_returns_active_sessions(self) -> None:
        token_hash = hashlib.sha256(b"cli_test_1").hexdigest()
        session = CliSession.objects.create(
            user=self.user,
            token_hash=token_hash,
            device_name="Work Laptop",
            expires_at=timezone.now() + timedelta(days=7),
            is_active=True,
        )

        url = reverse("api_v1:accounts:cli-sessions")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["device_name"], "Work Laptop")
        self.assertEqual(data[0]["id"], str(session.id))

    def test_cli_revoke_view_revokes_specified_session(self) -> None:
        token_hash = hashlib.sha256(b"cli_test_2").hexdigest()
        session = CliSession.objects.create(
            user=self.user,
            token_hash=token_hash,
            device_name="Old Terminal",
            expires_at=timezone.now() + timedelta(days=7),
            is_active=True,
        )

        url = reverse("api_v1:accounts:cli-revoke")
        response = self.client.post(url, {"session_id": str(session.id)}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        session.refresh_from_db()
        self.assertFalse(session.is_active)

    @patch("apps.accounts.views.firebase_service.revoke_refresh_tokens")
    def test_logout_view_revokes_tokens(self, mock_revoke) -> None:
        url = reverse("api_v1:accounts:logout")
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"status": "logged_out"})
        mock_revoke.assert_called_once_with(self.user.firebase_uid)

    def test_logout_view_unauthenticated_is_idempotent(self) -> None:
        unauth_client = APIClient()
        url = reverse("api_v1:accounts:logout")
        response = unauth_client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"status": "logged_out"})

    def test_cors_preflight_on_me_view_succeeds_without_auth(self) -> None:
        unauth_client = APIClient()
        url = reverse("api_v1:accounts:me")
        response = unauth_client.options(
            url,
            HTTP_ORIGIN="http://localhost:3000",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization,content-type,x-correlation-id",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "http://localhost:3000")

    def test_cors_preflight_on_logout_view_succeeds_without_auth(self) -> None:
        unauth_client = APIClient()
        url = reverse("api_v1:accounts:logout")
        response = unauth_client.options(
            url,
            HTTP_ORIGIN="http://localhost:3000",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization,content-type,x-correlation-id",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "http://localhost:3000")


class PermissionsTests(TestCase):
    """Test suite for custom role and state permissions."""

    def setUp(self) -> None:
        self.member_user = User.objects.create(
            firebase_uid="fb_member",
            email="member@nex.dev",
            role=User.Role.MEMBER,
            email_verified=False,
            is_active=True,
        )
        self.dev_user = User.objects.create(
            firebase_uid="fb_dev",
            email="dev@nex.dev",
            role=User.Role.DEVELOPER,
            email_verified=True,
            is_active=True,
        )
        self.admin_user = User.objects.create(
            firebase_uid="fb_admin",
            email="admin@nex.dev",
            role=User.Role.ADMIN,
            email_verified=True,
            is_active=True,
        )

    def test_is_developer_or_admin_permission(self) -> None:
        perm = IsDeveloperOrAdmin()
        mock_view = None

        class MockReq:
            def __init__(self, u):
                self.user = u

        self.assertFalse(perm.has_permission(MockReq(self.member_user), mock_view))
        self.assertTrue(perm.has_permission(MockReq(self.dev_user), mock_view))
        self.assertTrue(perm.has_permission(MockReq(self.admin_user), mock_view))

    def test_is_admin_role_permission(self) -> None:
        perm = IsAdminRole()
        mock_view = None

        class MockReq:
            def __init__(self, u):
                self.user = u

        self.assertFalse(perm.has_permission(MockReq(self.member_user), mock_view))
        self.assertFalse(perm.has_permission(MockReq(self.dev_user), mock_view))
        self.assertTrue(perm.has_permission(MockReq(self.admin_user), mock_view))

    def test_is_email_verified_permission(self) -> None:
        perm = IsEmailVerified()
        mock_view = None

        class MockReq:
            def __init__(self, u):
                self.user = u

        self.assertFalse(perm.has_permission(MockReq(self.member_user), mock_view))
        self.assertTrue(perm.has_permission(MockReq(self.dev_user), mock_view))
