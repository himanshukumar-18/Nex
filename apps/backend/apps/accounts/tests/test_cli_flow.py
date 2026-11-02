"""
NEX Accounts — Tests for CLI OAuth 2.0 PKCE Authorization Flow (RFC 7636 / RFC 8252).
"""

import base64
import hashlib
import secrets
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import CliAuthorizationCode, CliSession, User


class CliPkceFlowTests(TestCase):
    """Integration test suite for the CLI PKCE login flow."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = User.objects.create(
            firebase_uid="fb_pkce_user",
            email="pkce_user@nex.dev",
            role=User.Role.DEVELOPER,
            is_active=True,
        )
        self.client.force_authenticate(user=self.user)

        # Generate a valid RFC 7636 verifier and S256 challenge
        self.code_verifier = secrets.token_urlsafe(64)  # 86 chars, within 43-128
        digest = hashlib.sha256(self.code_verifier.encode("ascii")).digest()
        self.code_challenge = (
            base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        )
        self.redirect_uri = "http://127.0.0.1:8942/callback"
        self.state = secrets.token_urlsafe(32)

    def test_authorize_success_creates_code(self) -> None:
        url = reverse("api_v1:accounts:cli-authorize")
        payload = {
            "code_challenge": self.code_challenge,
            "code_challenge_method": "S256",
            "redirect_uri": self.redirect_uri,
            "state": self.state,
            "device_name": "MacBook Pro",
        }

        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()

        self.assertIn("authorization_code", data)
        self.assertEqual(data["redirect_uri"], self.redirect_uri)
        self.assertEqual(data["state"], self.state)

        # Verify record in database
        code_hash = hashlib.sha256(
            data["authorization_code"].encode("utf-8")
        ).hexdigest()
        auth_code_record = CliAuthorizationCode.objects.filter(
            code_hash=code_hash
        ).first()
        self.assertIsNotNone(auth_code_record)
        self.assertEqual(auth_code_record.user, self.user)
        self.assertFalse(auth_code_record.is_redeemed)

    def test_authorize_rejects_non_loopback_redirect_uri(self) -> None:
        url = reverse("api_v1:accounts:cli-authorize")
        payload = {
            "code_challenge": self.code_challenge,
            "code_challenge_method": "S256",
            "redirect_uri": "https://malicious-site.com/callback",
            "state": self.state,
        }

        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_authorize_rejects_plain_challenge_method(self) -> None:
        url = reverse("api_v1:accounts:cli-authorize")
        payload = {
            "code_challenge": self.code_challenge,
            "code_challenge_method": "plain",
            "redirect_uri": self.redirect_uri,
            "state": self.state,
        }

        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_full_successful_pkce_exchange(self) -> None:
        # Step 1: Authorize (web client)
        auth_url = reverse("api_v1:accounts:cli-authorize")
        auth_resp = self.client.post(
            auth_url,
            {
                "code_challenge": self.code_challenge,
                "code_challenge_method": "S256",
                "redirect_uri": self.redirect_uri,
                "state": self.state,
                "device_name": "Terminal Client",
            },
            format="json",
        )
        self.assertEqual(auth_resp.status_code, status.HTTP_201_CREATED)
        auth_code = auth_resp.json()["authorization_code"]

        # Step 2: Exchange (unauthenticated CLI client)
        unauth_client = APIClient()
        token_url = reverse("api_v1:accounts:cli-token")
        exchange_resp = unauth_client.post(
            token_url,
            {
                "code": auth_code,
                "code_verifier": self.code_verifier,
                "redirect_uri": self.redirect_uri,
            },
            format="json",
        )
        self.assertEqual(exchange_resp.status_code, status.HTTP_200_OK)
        token_data = exchange_resp.json()

        self.assertIn("access_token", token_data)
        self.assertTrue(token_data["access_token"].startswith("nex_cli_"))
        self.assertEqual(token_data["token_type"], "Bearer")
        self.assertEqual(token_data["user"]["email"], self.user.email)

        # Verify auth code is burned
        code_hash = hashlib.sha256(auth_code.encode("utf-8")).hexdigest()
        code_record = CliAuthorizationCode.objects.get(code_hash=code_hash)
        self.assertTrue(code_record.is_redeemed)

        # Verify CLI session exists
        cli_token_hash = hashlib.sha256(
            token_data["access_token"].encode("utf-8")
        ).hexdigest()
        session = CliSession.objects.filter(token_hash=cli_token_hash).first()
        self.assertIsNotNone(session)
        self.assertTrue(session.is_active)
        self.assertEqual(session.user, self.user)

    def test_replay_attack_with_same_code_fails(self) -> None:
        # Step 1: Authorize
        auth_url = reverse("api_v1:accounts:cli-authorize")
        auth_resp = self.client.post(
            auth_url,
            {
                "code_challenge": self.code_challenge,
                "code_challenge_method": "S256",
                "redirect_uri": self.redirect_uri,
                "state": self.state,
            },
            format="json",
        )
        auth_code = auth_resp.json()["authorization_code"]

        unauth_client = APIClient()
        token_url = reverse("api_v1:accounts:cli-token")
        payload = {
            "code": auth_code,
            "code_verifier": self.code_verifier,
            "redirect_uri": self.redirect_uri,
        }

        # First exchange succeeds
        first_resp = unauth_client.post(token_url, payload, format="json")
        self.assertEqual(first_resp.status_code, status.HTTP_200_OK)

        # Second exchange (replay) MUST fail with 400 invalid_grant
        second_resp = unauth_client.post(token_url, payload, format="json")
        self.assertEqual(second_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(second_resp.json()["error"], "invalid_grant")

    def test_exchange_fails_and_burns_code_on_verifier_mismatch(self) -> None:
        # Step 1: Authorize
        auth_url = reverse("api_v1:accounts:cli-authorize")
        auth_resp = self.client.post(
            auth_url,
            {
                "code_challenge": self.code_challenge,
                "code_challenge_method": "S256",
                "redirect_uri": self.redirect_uri,
                "state": self.state,
            },
            format="json",
        )
        auth_code = auth_resp.json()["authorization_code"]

        unauth_client = APIClient()
        token_url = reverse("api_v1:accounts:cli-token")
        wrong_verifier = secrets.token_urlsafe(64)  # Invalid verifier

        response = unauth_client.post(
            token_url,
            {
                "code": auth_code,
                "code_verifier": wrong_verifier,
                "redirect_uri": self.redirect_uri,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["error"], "invalid_grant")

        # Verify the authorization code is now burned
        code_hash = hashlib.sha256(auth_code.encode("utf-8")).hexdigest()
        code_record = CliAuthorizationCode.objects.get(code_hash=code_hash)
        self.assertTrue(code_record.is_redeemed)

    def test_exchange_fails_on_expired_code(self) -> None:
        raw_code = "expired_auth_code_xyz123"
        code_hash = hashlib.sha256(raw_code.encode("utf-8")).hexdigest()
        CliAuthorizationCode.objects.create(
            user=self.user,
            code_hash=code_hash,
            code_challenge=self.code_challenge,
            code_challenge_method="S256",
            redirect_uri=self.redirect_uri,
            state=self.state,
            is_redeemed=False,
            expires_at=timezone.now() - timedelta(minutes=1),  # Expired
        )

        unauth_client = APIClient()
        token_url = reverse("api_v1:accounts:cli-token")
        response = unauth_client.post(
            token_url,
            {
                "code": raw_code,
                "code_verifier": self.code_verifier,
                "redirect_uri": self.redirect_uri,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["error"], "invalid_grant")
