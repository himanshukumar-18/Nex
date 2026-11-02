"""
NEX Accounts — Tests for Firebase and CLI token authentication backends.
"""

import hashlib
from datetime import timedelta
from unittest.mock import patch

from django.test import RequestFactory, TestCase
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed

from apps.accounts.authentication import (
    CLI_TOKEN_PREFIX,
    CliTokenAuthentication,
    FirebaseAuthentication,
)
from apps.accounts.models import CliSession, User
from apps.accounts.services.firebase import (
    ExpiredTokenError,
    InvalidTokenError,
    RevokedTokenError,
)


class FirebaseAuthenticationTests(TestCase):
    """Test suite for FirebaseAuthentication backend."""

    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.backend = FirebaseAuthentication()

    def test_missing_auth_header_returns_none(self) -> None:
        request = self.factory.get("/api/v1/auth/me/")
        result = self.backend.authenticate(request)
        self.assertIsNone(result)

    def test_cli_token_is_skipped(self) -> None:
        request = self.factory.get(
            "/api/v1/auth/me/",
            HTTP_AUTHORIZATION="Bearer nex_cli_mock_token_abc123",
        )
        result = self.backend.authenticate(request)
        self.assertIsNone(result)

    @patch("apps.accounts.authentication.firebase_service.verify_id_token")
    def test_valid_token_creates_new_user(self, mock_verify) -> None:
        mock_verify.return_value = {
            "uid": "fb_user_123",
            "email": "developer@nex.dev",
            "email_verified": True,
            "name": "Alex Nex",
            "picture": "https://nex.dev/avatar.png",
            "firebase": {"sign_in_provider": "google.com"},
        }

        request = self.factory.get(
            "/api/v1/auth/me/",
            HTTP_AUTHORIZATION="Bearer mock_valid_jwt_token",
        )
        result = self.backend.authenticate(request)
        self.assertIsNotNone(result)
        user, claims = result

        self.assertEqual(user.firebase_uid, "fb_user_123")
        self.assertEqual(user.email, "developer@nex.dev")
        self.assertTrue(user.email_verified)
        self.assertEqual(user.display_name, "Alex Nex")
        self.assertEqual(user.avatar_url, "https://nex.dev/avatar.png")
        self.assertTrue(user.is_active)
        self.assertEqual(claims["uid"], "fb_user_123")

    @patch("apps.accounts.authentication.firebase_service.verify_id_token")
    def test_valid_token_updates_existing_user(self, mock_verify) -> None:
        user = User.objects.create(
            firebase_uid="fb_user_existing",
            email="old_email@nex.dev",
            email_verified=False,
            display_name="Old Name",
        )

        mock_verify.return_value = {
            "uid": "fb_user_existing",
            "email": "updated_email@nex.dev",
            "email_verified": True,
            "name": "New Name",
            "picture": "https://nex.dev/new.png",
            "firebase": {"sign_in_provider": "github.com"},
        }

        request = self.factory.get(
            "/api/v1/auth/me/",
            HTTP_AUTHORIZATION="Bearer mock_updated_jwt_token",
        )
        result = self.backend.authenticate(request)
        self.assertIsNotNone(result)
        auth_user, _ = result

        self.assertEqual(auth_user.id, user.id)
        self.assertEqual(auth_user.email, "updated_email@nex.dev")
        self.assertTrue(auth_user.email_verified)
        self.assertEqual(auth_user.display_name, "New Name")

    @patch("apps.accounts.authentication.firebase_service.verify_id_token")
    def test_inactive_user_raises_authentication_failed(self, mock_verify) -> None:
        User.objects.create(
            firebase_uid="fb_user_disabled",
            email="disabled@nex.dev",
            is_active=False,
        )

        mock_verify.return_value = {
            "uid": "fb_user_disabled",
            "email": "disabled@nex.dev",
            "email_verified": True,
        }

        request = self.factory.get(
            "/api/v1/auth/me/",
            HTTP_AUTHORIZATION="Bearer mock_disabled_token",
        )
        with self.assertRaises(AuthenticationFailed) as ctx:
            self.backend.authenticate(request)
        self.assertIn("deactivated", str(ctx.exception))

    @patch("apps.accounts.authentication.firebase_service.verify_id_token")
    def test_expired_token_raises_authentication_failed(self, mock_verify) -> None:
        mock_verify.side_effect = ExpiredTokenError("Token expired")
        request = self.factory.get(
            "/api/v1/auth/me/",
            HTTP_AUTHORIZATION="Bearer mock_expired_token",
        )
        with self.assertRaises(AuthenticationFailed) as ctx:
            self.backend.authenticate(request)
        self.assertIn("expired", str(ctx.exception).lower())

    @patch("apps.accounts.authentication.firebase_service.verify_id_token")
    def test_revoked_token_raises_authentication_failed(self, mock_verify) -> None:
        mock_verify.side_effect = RevokedTokenError("Token revoked")
        request = self.factory.get(
            "/api/v1/auth/me/",
            HTTP_AUTHORIZATION="Bearer mock_revoked_token",
        )
        with self.assertRaises(AuthenticationFailed) as ctx:
            self.backend.authenticate(request)
        self.assertIn("revoked", str(ctx.exception).lower())

    @patch("apps.accounts.authentication.firebase_service.verify_id_token")
    def test_invalid_token_raises_authentication_failed(self, mock_verify) -> None:
        mock_verify.side_effect = InvalidTokenError("Invalid token")
        request = self.factory.get(
            "/api/v1/auth/me/",
            HTTP_AUTHORIZATION="Bearer mock_garbage_token",
        )
        with self.assertRaises(AuthenticationFailed) as ctx:
            self.backend.authenticate(request)
        self.assertIn("invalid", str(ctx.exception).lower())

    @patch("apps.accounts.authentication.firebase_service.verify_id_token")
    def test_missing_email_provisions_with_fallback_address(self, mock_verify) -> None:
        mock_verify.return_value = {
            "uid": "fb_github_no_email_uid",
            "email": None,
            "name": "GitHub Private User",
            "firebase": {"sign_in_provider": "github.com"},
        }
        request = self.factory.get(
            "/api/v1/auth/me/",
            HTTP_AUTHORIZATION="Bearer mock_no_email_token",
        )
        result = self.backend.authenticate(request)
        self.assertIsNotNone(result)
        user, _ = result
        self.assertEqual(user.firebase_uid, "fb_github_no_email_uid")
        self.assertTrue(user.email.endswith("@users.nex.local"))
        self.assertFalse(user.email_verified)

    @patch("apps.accounts.authentication.firebase_service.verify_id_token")
    def test_duplicate_email_with_different_uid_raises_authentication_failed(
        self, mock_verify
    ) -> None:
        User.objects.create(
            firebase_uid="uid_existing_primary",
            email="shared@nex.dev",
            email_verified=True,
        )
        mock_verify.return_value = {
            "uid": "uid_new_colliding",
            "email": "shared@nex.dev",
            "firebase": {"sign_in_provider": "github.com"},
        }
        request = self.factory.get(
            "/api/v1/auth/me/",
            HTTP_AUTHORIZATION="Bearer mock_colliding_token",
        )
        with self.assertRaises(AuthenticationFailed) as ctx:
            self.backend.authenticate(request)
        self.assertIn("already exists", str(ctx.exception))



class CliTokenAuthenticationTests(TestCase):
    """Test suite for CliTokenAuthentication backend."""

    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.backend = CliTokenAuthentication()
        self.user = User.objects.create(
            firebase_uid="fb_cli_test_uid",
            email="cli_user@nex.dev",
            role=User.Role.DEVELOPER,
            is_active=True,
        )

    def test_firebase_token_is_skipped(self) -> None:
        request = self.factory.get(
            "/api/v1/auth/me/",
            HTTP_AUTHORIZATION="Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6...",
        )
        result = self.backend.authenticate(request)
        self.assertIsNone(result)

    def test_valid_cli_token_authenticates_user(self) -> None:
        raw_token = f"{CLI_TOKEN_PREFIX}secret_random_token_12345"
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        session = CliSession.objects.create(
            user=self.user,
            token_hash=token_hash,
            device_name="MacBook Pro",
            expires_at=timezone.now() + timedelta(days=30),
            is_active=True,
        )

        request = self.factory.get(
            "/api/v1/auth/me/",
            HTTP_AUTHORIZATION=f"Bearer {raw_token}",
        )
        result = self.backend.authenticate(request)
        self.assertIsNotNone(result)
        auth_user, auth_session = result

        self.assertEqual(auth_user.id, self.user.id)
        self.assertEqual(auth_session.id, session.id)

    def test_expired_cli_session_is_rejected_and_deactivated(self) -> None:
        raw_token = f"{CLI_TOKEN_PREFIX}expired_token_12345"
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        session = CliSession.objects.create(
            user=self.user,
            token_hash=token_hash,
            device_name="MacBook Pro",
            expires_at=timezone.now() - timedelta(days=1),  # Expired
            is_active=True,
        )

        request = self.factory.get(
            "/api/v1/auth/me/",
            HTTP_AUTHORIZATION=f"Bearer {raw_token}",
        )
        with self.assertRaises(AuthenticationFailed) as ctx:
            self.backend.authenticate(request)
        self.assertIn("expired", str(ctx.exception).lower())

        session.refresh_from_db()
        self.assertFalse(session.is_active)

    def test_revoked_cli_session_is_rejected(self) -> None:
        raw_token = f"{CLI_TOKEN_PREFIX}revoked_token_12345"
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        CliSession.objects.create(
            user=self.user,
            token_hash=token_hash,
            device_name="MacBook Pro",
            expires_at=timezone.now() + timedelta(days=30),
            is_active=False,  # Revoked
        )

        request = self.factory.get(
            "/api/v1/auth/me/",
            HTTP_AUTHORIZATION=f"Bearer {raw_token}",
        )
        with self.assertRaises(AuthenticationFailed):
            self.backend.authenticate(request)
