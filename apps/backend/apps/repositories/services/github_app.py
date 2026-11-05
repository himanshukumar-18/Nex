"""NEX Repositories — GitHub App Authentication & Token Management Service.

Provides secure RS256 JWT generation for GitHub App authentication, short-lived
installation access token management with Redis caching, HMAC-SHA256 webhook
signature verification, and cryptographic state generation for authorization flows.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import time
from typing import Any

import httpx
import jwt
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from django.conf import settings
from django.core.cache import cache
from django.utils.dateparse import parse_datetime

logger = logging.getLogger(__name__)

GITHUB_API_BASE_URL = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"
USER_AGENT = "NEX-AI-Software-Engineer/1.0"


class GitHubAppError(Exception):
    """Base exception for all GitHub App service operations."""


class GitHubAppConfigurationError(GitHubAppError):
    """Raised when GitHub App configuration (App ID or Private Key) is missing or invalid."""


class GitHubInstallationNotFoundError(GitHubAppError):
    """Raised when a specified GitHub installation does not exist or has been deleted."""


class GitHubAppAuthenticationError(GitHubAppError):
    """Raised when GitHub rejects App JWT or installation authentication."""


class GitHubAppService:
    """Manages GitHub App lifecycle, installation access tokens, and webhook security."""

    @classmethod
    def _validate_pem_key(cls, pem_data: str) -> bool:
        """Validate whether pem_data represents a valid RSA private key using cryptography."""
        if not pem_data or "PRIVATE KEY" not in pem_data:
            return False
        normalized = pem_data.replace("\\n", "\n").strip().encode("utf-8")
        try:
            load_pem_private_key(normalized, password=None)
            return True
        except Exception:
            return False

    @classmethod
    def is_configured(cls) -> bool:
        """Check whether GitHub App credentials are configured and valid."""
        app_id = getattr(settings, "GITHUB_APP_ID", "")
        if not app_id:
            return False
        try:
            cls.get_private_key()
            return True
        except GitHubAppConfigurationError:
            return False

    @classmethod
    def get_private_key(cls) -> str:
        """Load and validate RSA private key from environment string or mounted secret path.

        Validates PEM key using cryptography library. Rejects SHA256 fingerprints
        and invalid inline keys, falling back to GITHUB_APP_PRIVATE_KEY_PATH.
        Never logs actual private key contents, JWTs, fingerprints or tokens.
        """
        # 1. Attempt to load inline private key if configured
        key_content = getattr(settings, "GITHUB_APP_PRIVATE_KEY", "")
        if key_content:
            clean_content = key_content.strip()
            if cls._validate_pem_key(clean_content):
                return clean_content.replace("\\n", "\n")
            logger.warning(
                "GITHUB_APP_PRIVATE_KEY inline content is not a valid PEM private key "
                "(e.g. fingerprint or invalid format). Falling back to GITHUB_APP_PRIVATE_KEY_PATH."
            )

        # 2. Fall back to mounted or configured file path
        key_path = getattr(settings, "GITHUB_APP_PRIVATE_KEY_PATH", "")
        if key_path and os.path.exists(key_path):
            try:
                with open(key_path, "r", encoding="utf-8") as f:
                    file_content = f.read().strip()
                if cls._validate_pem_key(file_content):
                    return file_content
                logger.error("GitHub App private key file at '%s' is not a valid PEM private key.", key_path)
            except OSError as exc:
                raise GitHubAppConfigurationError(
                    f"Failed to read GitHub App private key from path '{key_path}': {exc}"
                ) from exc

        raise GitHubAppConfigurationError(
            "GitHub App private key is not configured or invalid. "
            "Please provide a valid RSA PEM private key via GITHUB_APP_PRIVATE_KEY "
            "or mount the PEM file at GITHUB_APP_PRIVATE_KEY_PATH."
        )

    @classmethod
    def generate_app_jwt(cls) -> str:
        """Generate a short-lived RS256 JWT for authenticating as the GitHub App.

        GitHub requires:
        - Algorithm: RS256
        - iss: GitHub App ID
        - iat: Issued at (now - 60s for clock drift)
        - exp: Expiration (max 10 minutes; we use 9 minutes)
        """
        app_id = getattr(settings, "GITHUB_APP_ID", "")
        if not app_id:
            raise GitHubAppConfigurationError("GITHUB_APP_ID is not configured in settings.")

        private_key = cls.get_private_key()
        now = int(time.time())

        payload = {
            "iat": now - 60,
            "exp": now + 540,  # 9 minutes
            "iss": str(app_id),
        }

        try:
            token = jwt.encode(payload, private_key, algorithm="RS256")
            return token if isinstance(token, str) else token.decode("utf-8")
        except Exception as exc:
            raise GitHubAppConfigurationError(f"Failed to sign GitHub App JWT: {exc}") from exc

    @classmethod
    def get_headers(cls, app_jwt: str | None = None, token: str | None = None) -> dict[str, str]:
        """Construct standard GitHub REST API headers."""
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
            "User-Agent": USER_AGENT,
        }
        if token:
            headers["Authorization"] = f"token {token}"
        elif app_jwt:
            headers["Authorization"] = f"Bearer {app_jwt}"
        return headers

    @classmethod
    def get_installation(cls, installation_id: int) -> dict[str, Any]:
        """Query GitHub API to retrieve installation metadata and verify ownership.

        Args:
            installation_id: Numeric GitHub installation ID.

        Returns:
            Dictionary containing verified installation metadata from GitHub.

        Raises:
            GitHubInstallationNotFoundError: If installation does not exist (HTTP 404).
            GitHubAppAuthenticationError: If App JWT is rejected (HTTP 401).
            GitHubAppError: On other API errors.
        """
        app_jwt = cls.generate_app_jwt()
        headers = cls.get_headers(app_jwt=app_jwt)
        url = f"{GITHUB_API_BASE_URL}/app/installations/{installation_id}"

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url, headers=headers)

                if response.status_code == 404:
                    raise GitHubInstallationNotFoundError(
                        f"GitHub installation {installation_id} was not found or was revoked."
                    )
                if response.status_code == 401:
                    raise GitHubAppAuthenticationError(
                        "GitHub rejected the App JWT credentials. Verify App ID and Private Key."
                    )
                if response.is_error:
                    raise GitHubAppError(
                        f"GitHub API error (HTTP {response.status_code}): {response.text}"
                    )

                return response.json()
        except httpx.RequestError as exc:
            raise GitHubAppError(f"Failed to connect to GitHub API: {exc}") from exc

    @classmethod
    def get_installation_access_token(
        cls,
        installation_id: int,
        permissions: dict[str, str] | None = None,
        force_refresh: bool = False,
    ) -> str:
        """Obtain a short-lived (1 hour) installation access token with Redis caching.

        Args:
            installation_id: Target installation ID.
            permissions: Optional permission subset (least privilege).
            force_refresh: If True, bypasses cache and mints a fresh token.

        Returns:
            The raw token string (e.g. 'ghs_...').
        """
        cache_key = f"github:token:{installation_id}"

        if not force_refresh:
            cached_token = cache.get(cache_key)
            if cached_token:
                return str(cached_token)

        app_jwt = cls.generate_app_jwt()
        headers = cls.get_headers(app_jwt=app_jwt)
        url = f"{GITHUB_API_BASE_URL}/app/installations/{installation_id}/access_tokens"

        body: dict[str, Any] = {}
        if permissions:
            body["permissions"] = permissions

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(url, headers=headers, json=body or None)

                if response.status_code == 404:
                    raise GitHubInstallationNotFoundError(
                        f"GitHub installation {installation_id} not found."
                    )
                if response.status_code == 401:
                    raise GitHubAppAuthenticationError("GitHub rejected token request.")
                if response.is_error:
                    raise GitHubAppError(
                        f"GitHub token request failed (HTTP {response.status_code}): {response.text}"
                    )

                data = response.json()
                token = data["token"]
                expires_at_str = data.get("expires_at")

                # Calculate cache TTL (expire 5 minutes prior to actual expiration)
                ttl_seconds = 3000  # Default ~50 minutes
                if expires_at_str:
                    exp_dt = parse_datetime(expires_at_str)
                    if exp_dt:
                        diff = (exp_dt.timestamp() - time.time()) - 300
                        if diff > 60:
                            ttl_seconds = int(diff)

                cache.set(cache_key, token, timeout=ttl_seconds)
                return token
        except httpx.RequestError as exc:
            raise GitHubAppError(f"Network error requesting installation token: {exc}") from exc

    @classmethod
    def revoke_cached_token(cls, installation_id: int) -> None:
        """Invalidate any cached installation access token in Redis."""
        cache_key = f"github:token:{installation_id}"
        cache.delete(cache_key)

    @classmethod
    def generate_authorization_state(cls, user_id: str) -> str:
        """Generate a cryptographically secure random state token bound to a NEX user.

        TTL is 600 seconds (10 minutes).
        """
        state = secrets.token_urlsafe(32)
        cache_key = f"github:auth_state:{state}"
        cache.set(cache_key, user_id, timeout=600)
        return state

    @classmethod
    def consume_authorization_state(cls, state: str) -> str | None:
        """Validate and atomically burn an authorization state token to prevent replay attacks.

        Returns:
            The associated user_id string if valid, or None if invalid/expired.
        """
        if not state or len(state) < 16:
            return None

        cache_key = f"github:auth_state:{state}"
        user_id = cache.get(cache_key)
        if user_id:
            # Single-use burn
            cache.delete(cache_key)
            return str(user_id)
        return None

    @classmethod
    def get_installation_url(cls, state: str) -> str:
        """Construct the official GitHub App installation URL with state parameter."""
        slug = getattr(settings, "GITHUB_APP_SLUG", "nex-engineering-assistant")
        return f"https://github.com/apps/{slug}/installations/new?state={state}"

    @classmethod
    def verify_webhook_signature(cls, payload_bytes: bytes, signature_header: str | None) -> bool:
        """Verify GitHub webhook payload signature using HMAC-SHA256 constant-time comparison.

        Args:
            payload_bytes: Raw HTTP request body bytes.
            signature_header: Raw value of the 'X-Hub-Signature-256' header.

        Returns:
            True if the signature is valid; False otherwise.
        """
        secret = getattr(settings, "GITHUB_WEBHOOK_SECRET", "")
        if not secret or not signature_header:
            return False

        if not signature_header.startswith("sha256="):
            return False

        expected_signature = "sha256=" + hmac.new(
            secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected_signature, signature_header)

