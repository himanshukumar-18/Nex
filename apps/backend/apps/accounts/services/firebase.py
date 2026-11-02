"""
NEX Backend — Firebase Admin SDK Integration Service.

Provides secure token verification, token revocation, and user identity handling.
Ensures Firebase credentials are securely loaded without leaking to logs or responses.
"""

import json
import logging
import os
from typing import Any

import firebase_admin
from django.conf import settings
from firebase_admin import auth, credentials
from google.auth.exceptions import DefaultCredentialsError

logger = logging.getLogger(__name__)


class FirebaseServiceError(Exception):
    """Base exception for all Firebase service operations."""


class InvalidTokenError(FirebaseServiceError):
    """Raised when an ID token is invalid or malformed."""


class ExpiredTokenError(InvalidTokenError):
    """Raised when an ID token has expired."""


class RevokedTokenError(InvalidTokenError):
    """Raised when an ID token has been explicitly revoked."""


class FirebaseServiceUnavailableError(FirebaseServiceError):
    """Raised when Firebase public keys or service cannot be reached."""


class FirebaseAdminService:
    """
    Manages the Firebase Admin SDK lifecycle and provides authentication operations.
    """

    _app: firebase_admin.App | None = None

    @classmethod
    def initialize(cls) -> firebase_admin.App | None:
        """
        Idempotently initializes the Firebase Admin SDK application.
        Supports service account file path, raw JSON credential string, or default credentials.
        """
        if cls._app is not None:
            return cls._app

        if firebase_admin._apps:
            cls._app = firebase_admin.get_app()
            return cls._app

        cred_path = getattr(settings, "FIREBASE_CREDENTIALS_PATH", "")
        cred_json = getattr(settings, "FIREBASE_CREDENTIALS_JSON", "")
        project_id = getattr(settings, "FIREBASE_PROJECT_ID", "")

        cred = None
        try:
            if cred_json:
                cert_dict = json.loads(cred_json)
                cred = credentials.Certificate(cert_dict)
            elif cred_path and os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
            elif project_id:
                # Default application credentials or mock in testing
                try:
                    cred = credentials.ApplicationDefault()
                except Exception:
                    cred = None
        except Exception as exc:
            logger.warning(
                "Failed to load Firebase credentials: %s. Using default initialization.",
                str(exc),
            )
            cred = None

        options = {}
        if project_id:
            options["projectId"] = project_id

        try:
            if cred:
                cls._app = firebase_admin.initialize_app(cred, options=options or None)
            elif project_id:
                cls._app = firebase_admin.initialize_app(options=options)
            else:
                # Dev/test without credentials configured
                cls._app = firebase_admin.initialize_app()
            logger.info("Firebase Admin SDK initialized successfully.")
        except ValueError:
            # Already initialized
            cls._app = firebase_admin.get_app()
        except Exception as exc:
            logger.warning(
                "Firebase Admin SDK initialization skipped/failed: %s", str(exc)
            )
            cls._app = None

        return cls._app

    @classmethod
    def verify_id_token(
        cls, id_token: str, check_revoked: bool = False
    ) -> dict[str, Any]:
        """
        Verifies the given Firebase ID token using the Firebase Admin SDK.

        Args:
            id_token: The raw JWT string from the Authorization header.
            check_revoked: Whether to check if the token has been revoked.

        Returns:
            dict containing decoded claims (uid, email, email_verified, name, picture, etc.).

        Raises:
            ExpiredTokenError: If the token has expired.
            RevokedTokenError: If the token was revoked.
            InvalidTokenError: If the token is invalid or signatures don't match.
            FirebaseServiceUnavailableError: If Firebase public keys cannot be retrieved.
        """
        if not id_token or not isinstance(id_token, str):
            raise InvalidTokenError("ID token must be a non-empty string.")

        cls.initialize()

        try:
            decoded_claims = auth.verify_id_token(
                id_token,
                app=cls._app,
                check_revoked=check_revoked,
            )
            return decoded_claims
        except auth.ExpiredIdTokenError as exc:
            logger.info("Firebase ID token has expired: %s", str(exc))
            raise ExpiredTokenError("Firebase ID token has expired.") from exc
        except auth.RevokedIdTokenError as exc:
            logger.warning("Firebase ID token was revoked: %s", str(exc))
            raise RevokedTokenError("Firebase ID token has been revoked.") from exc
        except auth.InvalidIdTokenError as exc:
            logger.warning("Invalid Firebase ID token received.")
            raise InvalidTokenError("Invalid Firebase ID token.") from exc
        except auth.CertificateFetchError as exc:
            logger.error("Failed to fetch Firebase public certs: %s", str(exc))
            raise FirebaseServiceUnavailableError(
                "Unable to reach Firebase authentication service."
            ) from exc
        except DefaultCredentialsError as exc:
            logger.error(
                "Firebase Admin server credentials not configured: %s. "
                "Configure FIREBASE_CREDENTIALS_PATH or FIREBASE_CREDENTIALS_JSON in .env.",
                str(exc),
            )
            raise FirebaseServiceUnavailableError(
                "Firebase Admin server credentials are not configured on the backend."
            ) from exc
        except Exception as exc:
            logger.error(
                "Unexpected error during Firebase token verification: %s", str(exc)
            )
            raise InvalidTokenError(f"Token verification failed: {exc}") from exc

    @classmethod
    def revoke_refresh_tokens(cls, uid: str) -> None:
        """
        Revokes all refresh tokens for the given Firebase user UID.
        Forces the user to re-authenticate on all devices.
        """
        if not uid:
            return
        cls.initialize()
        try:
            auth.revoke_refresh_tokens(uid, app=cls._app)
            logger.info("Revoked refresh tokens for user UID %s", uid)
        except Exception as exc:
            logger.error(
                "Failed to revoke refresh tokens for user UID %s: %s", uid, str(exc)
            )
            raise FirebaseServiceError(
                f"Failed to revoke user sessions: {exc}"
            ) from exc


firebase_service = FirebaseAdminService
