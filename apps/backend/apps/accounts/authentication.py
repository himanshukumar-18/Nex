"""
NEX Accounts — Authentication Backends for Django REST Framework.

Implements:
1. FirebaseAuthentication: Validates Firebase ID tokens for web frontend / mobile clients.
2. CliTokenAuthentication: Validates SHA-256 hashed CLI session tokens for NEX CLI.
"""

import hashlib
import logging
from typing import Any

from django.db import transaction
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

from apps.accounts.models import CliSession, User
from apps.accounts.services.firebase import (
    ExpiredTokenError,
    FirebaseServiceUnavailableError,
    InvalidTokenError,
    RevokedTokenError,
    firebase_service,
)
from apps.audit_logs.models import SecurityAuditEvent

logger = logging.getLogger(__name__)

CLI_TOKEN_PREFIX = "nex_cli_"


class FirebaseAuthentication(BaseAuthentication):
    """
    Authenticates requests bearing a Firebase ID token.
    Header format: Authorization: Bearer <firebase_id_token>

    Does not process tokens prefixed with 'nex_cli_', delegating those to CliTokenAuthentication.
    Syncs or creates local User records to maintain local authorization and role state.
    """

    def authenticate(self, request: Request) -> tuple[User, dict[str, Any]] | None:
        auth_header = get_authorization_header(request).decode("utf-8")
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None

        raw_token = parts[1]

        # Delegate CLI tokens to CliTokenAuthentication
        if raw_token.startswith(CLI_TOKEN_PREFIX):
            return None

        try:
            claims = firebase_service.verify_id_token(raw_token, check_revoked=True)
        except ExpiredTokenError as exc:
            raise AuthenticationFailed("Authentication token has expired.") from exc
        except RevokedTokenError as exc:
            raise AuthenticationFailed(
                "Authentication token has been revoked."
            ) from exc
        except FirebaseServiceUnavailableError as exc:
            raise AuthenticationFailed(
                "Authentication service is temporarily unavailable."
            ) from exc
        except InvalidTokenError as exc:
            raise AuthenticationFailed("Invalid authentication token.") from exc
        except Exception as exc:
            logger.warning(
                "Unexpected error during Firebase token verification: %s", str(exc)
            )
            raise AuthenticationFailed("Token verification failed.") from exc

        uid = claims.get("uid") or claims.get("sub")
        if not uid:
            raise AuthenticationFailed(
                "Authentication token missing subject identifier."
            )

        provider_data = claims.get("firebase", {})
        sign_in_provider = provider_data.get("sign_in_provider", "firebase")

        raw_email = (claims.get("email") or "").strip().lower()
        if raw_email:
            email = raw_email
        else:
            # Deterministic fallback for federated OAuth providers (e.g. GitHub private email)
            email = f"{sign_in_provider}_{uid[:16]}@users.nex.local"

        email_verified = bool(claims.get("email_verified", False))
        display_name = (claims.get("name") or "").strip()
        avatar_url = (claims.get("picture") or "").strip()

        # Provision or synchronize local authoritative User record atomically
        with transaction.atomic():
            user = (
                User.objects.select_for_update()
                .filter(firebase_uid=uid)
                .first()
            )
            created = False
            if not user:
                # Check if this email is already bound to another User record
                existing_by_email = (
                    User.objects.select_for_update()
                    .filter(email=email)
                    .first()
                )
                if existing_by_email:
                    # If existing record has no firebase_uid or matching UID, link it
                    if not existing_by_email.firebase_uid or existing_by_email.firebase_uid == uid:
                        existing_by_email.firebase_uid = uid
                        user = existing_by_email
                    else:
                        # Conflict: Email is already associated with another distinct Firebase UID
                        logger.warning(
                            "Identity conflict during provisioning: incoming UID %s has email %s "
                            "which is already bound to existing UID %s",
                            uid,
                            email,
                            existing_by_email.firebase_uid,
                        )
                        SecurityAuditEvent.record(
                            event_type=SecurityAuditEvent.EventType.AUTH_FAILURE,
                            request=request,
                            metadata={
                                "reason": "Email collision with existing account",
                                "uid": uid,
                            },
                        )
                        raise AuthenticationFailed(
                            "An account with this email address already exists. Please sign in with your original method."
                        )
                else:
                    user = User.objects.create(
                        firebase_uid=uid,
                        email=email,
                        email_verified=email_verified,
                        display_name=display_name,
                        avatar_url=avatar_url,
                        role=User.Role.MEMBER,
                        is_active=True,
                        last_login_at=timezone.now(),
                        metadata={"sign_in_provider": sign_in_provider},
                    )
                    created = True

            if created:
                SecurityAuditEvent.record(
                    event_type=SecurityAuditEvent.EventType.USER_PROVISIONED,
                    request=request,
                    user=user,
                    metadata={"sign_in_provider": sign_in_provider},
                )
                logger.info("Provisioned new local User for Firebase UID %s", uid)
            else:
                updated_fields = []
                if user.email != email:
                    if not User.objects.filter(email=email).exclude(pk=user.pk).exists():
                        user.email = email
                        updated_fields.append("email")
                if user.email_verified != email_verified:
                    user.email_verified = email_verified
                    updated_fields.append("email_verified")
                if display_name and user.display_name != display_name:
                    user.display_name = display_name
                    updated_fields.append("display_name")
                if avatar_url and user.avatar_url != avatar_url:
                    user.avatar_url = avatar_url
                    updated_fields.append("avatar_url")

                user.last_login_at = timezone.now()
                updated_fields.append("last_login_at")

                user.save(update_fields=updated_fields)

        if not user.is_active:
            SecurityAuditEvent.record(
                event_type=SecurityAuditEvent.EventType.AUTH_FAILURE,
                request=request,
                user=user,
                metadata={"reason": "User account is deactivated."},
            )
            raise AuthenticationFailed("User account has been deactivated.")

        return (user, claims)

    def authenticate_header(self, request: Request) -> str:
        return 'Bearer realm="api"'


class CliTokenAuthentication(BaseAuthentication):
    """
    Authenticates requests originating from the NEX CLI bearing a scoped CLI session token.
    Header format: Authorization: Bearer nex_cli_<token>
    """

    def authenticate(self, request: Request) -> tuple[User, CliSession] | None:
        auth_header = get_authorization_header(request).decode("utf-8")
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None

        raw_token = parts[1]

        # Only process tokens matching the CLI format
        if not raw_token.startswith(CLI_TOKEN_PREFIX):
            return None

        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        try:
            session = (
                CliSession.objects.select_related("user")
                .filter(token_hash=token_hash, is_active=True)
                .first()
            )
        except Exception as exc:
            logger.error("Error looking up CLI session: %s", str(exc))
            raise AuthenticationFailed("Authentication failed.") from exc

        if session is None:
            raise AuthenticationFailed("Invalid or expired CLI session token.")

        if not session.is_valid():
            session.is_active = False
            session.save(update_fields=["is_active"])
            raise AuthenticationFailed(
                "CLI session has expired. Please run 'nex login' to re-authenticate."
            )

        user = session.user
        if not user.is_active:
            raise AuthenticationFailed("User account has been deactivated.")

        # Update last_used_at on the session
        session.last_used_at = timezone.now()
        session.save(update_fields=["last_used_at"])

        return (user, session)

    def authenticate_header(self, request: Request) -> str:
        return 'Bearer realm="api"'
