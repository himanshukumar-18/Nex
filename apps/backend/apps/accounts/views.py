"""
NEX Accounts — Authentication and Identity REST API Views.

Implements user profile endpoints and RFC 7636 / RFC 8252 PKCE CLI authorization flow.
"""

import base64
import hashlib
import hmac
import logging
import secrets
from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import CliAuthorizationCode, CliSession
from apps.accounts.serializers import (
    CliAuthorizeRequestSerializer,
    CliSessionSerializer,
    CliTokenExchangeSerializer,
    UserProfileSerializer,
    UserProfileUpdateSerializer,
)
from apps.accounts.services.firebase import firebase_service
from apps.api.permissions import IsAuthenticatedUser
from apps.audit_logs.models import SecurityAuditEvent

logger = logging.getLogger(__name__)

CLI_TOKEN_PREFIX = "nex_cli_"
AUTH_CODE_LIFETIME = timedelta(minutes=5)
CLI_TOKEN_LIFETIME = timedelta(days=30)


class MeView(APIView):
    """
    Returns the currently authenticated user's authoritative profile.
    """

    permission_classes = [IsAuthenticatedUser]

    def get(self, request: Request) -> Response:
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SyncProfileView(APIView):
    """
    Updates mutable user profile details (display name, avatar).
    """

    permission_classes = [IsAuthenticatedUser]

    def post(self, request: Request) -> Response:
        serializer = UserProfileUpdateSerializer(
            request.user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        full_profile = UserProfileSerializer(request.user)
        return Response(full_profile.data, status=status.HTTP_200_OK)


class CliAuthorizeView(APIView):
    """
    Authorizes a CLI PKCE session request.
    Called by the web frontend after the user approves terminal access.

    Creates an ephemeral single-use CliAuthorizationCode and returns the raw code
    so the browser can redirect to the CLI loopback listener.
    """

    permission_classes = [IsAuthenticatedUser]

    def post(self, request: Request) -> Response:
        serializer = CliAuthorizeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        raw_code = secrets.token_urlsafe(32)
        code_hash = hashlib.sha256(raw_code.encode("utf-8")).hexdigest()
        expires_at = timezone.now() + AUTH_CODE_LIFETIME

        CliAuthorizationCode.objects.create(
            user=request.user,
            code_hash=code_hash,
            code_challenge=data["code_challenge"],
            code_challenge_method=data.get("code_challenge_method", "S256"),
            redirect_uri=data["redirect_uri"],
            state=data["state"],
            scopes=data.get("scopes", []),
            expires_at=expires_at,
        )

        SecurityAuditEvent.record(
            event_type=SecurityAuditEvent.EventType.CLI_LOGIN_INITIATED,
            request=request,
            user=request.user,
            metadata={
                "redirect_uri": data["redirect_uri"],
                "device_name": data.get("device_name", "Terminal Client"),
            },
        )

        return Response(
            {
                "authorization_code": raw_code,
                "redirect_uri": data["redirect_uri"],
                "state": data["state"],
                "expires_in": int(AUTH_CODE_LIFETIME.total_seconds()),
            },
            status=status.HTTP_201_CREATED,
        )


class CliTokenExchangeView(APIView):
    """
    Exchanges an authorization code and PKCE code verifier for a long-lived CLI session token.
    Public endpoint invoked by the local CLI loopback client.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = CliTokenExchangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        code_hash = hashlib.sha256(data["code"].encode("utf-8")).hexdigest()

        try:
            auth_code = (
                CliAuthorizationCode.objects.select_related("user")
                .filter(code_hash=code_hash)
                .first()
            )
        except Exception as exc:
            logger.error(
                "Database query failed during CLI token exchange: %s", str(exc)
            )
            return Response(
                {
                    "error": "server_error",
                    "error_description": "Internal database error.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if auth_code is None or not auth_code.is_valid():
            SecurityAuditEvent.record(
                event_type=SecurityAuditEvent.EventType.AUTH_FAILURE,
                request=request,
                metadata={
                    "reason": "Invalid, expired, or previously redeemed authorization code presented."
                },
            )
            return Response(
                {
                    "error": "invalid_grant",
                    "error_description": "Authorization code is invalid, expired, or already used.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate redirect URI strictly matches
        if auth_code.redirect_uri != data["redirect_uri"]:
            SecurityAuditEvent.record(
                event_type=SecurityAuditEvent.EventType.AUTH_FAILURE,
                request=request,
                user=auth_code.user,
                metadata={"reason": "Redirect URI mismatch during CLI token exchange."},
            )
            return Response(
                {
                    "error": "invalid_grant",
                    "error_description": "Redirect URI mismatch.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate PKCE S256 code verifier
        verifier = data["code_verifier"]
        verifier_digest = hashlib.sha256(verifier.encode("ascii")).digest()
        computed_challenge = (
            base64.urlsafe_b64encode(verifier_digest).decode("ascii").rstrip("=")
        )

        # Always redeem the authorization code to prevent replay attacks regardless of result
        auth_code.is_redeemed = True
        auth_code.save(update_fields=["is_redeemed", "updated_at"])

        if not hmac.compare_digest(computed_challenge, auth_code.code_challenge):
            SecurityAuditEvent.record(
                event_type=SecurityAuditEvent.EventType.AUTH_FAILURE,
                request=request,
                user=auth_code.user,
                metadata={"reason": "PKCE code verifier verification failed."},
            )
            return Response(
                {
                    "error": "invalid_grant",
                    "error_description": "PKCE code verifier does not match challenge.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = auth_code.user
        if not user.is_active:
            return Response(
                {
                    "error": "unauthorized_client",
                    "error_description": "User account is inactive.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Generate long-lived CLI token
        raw_cli_token = f"{CLI_TOKEN_PREFIX}{secrets.token_urlsafe(32)}"
        token_hash = hashlib.sha256(raw_cli_token.encode("utf-8")).hexdigest()
        expires_at = timezone.now() + CLI_TOKEN_LIFETIME

        session = CliSession.objects.create(
            user=user,
            token_hash=token_hash,
            device_name=request.data.get("device_name", "Terminal Client"),
            expires_at=expires_at,
            is_active=True,
        )

        SecurityAuditEvent.record(
            event_type=SecurityAuditEvent.EventType.CLI_LOGIN_COMPLETED,
            request=request,
            user=user,
            metadata={
                "client": "cli",
                "session_id": str(session.id),
                "device_name": session.device_name,
            },
        )

        return Response(
            {
                "access_token": raw_cli_token,
                "token_type": "Bearer",
                "expires_in": int(CLI_TOKEN_LIFETIME.total_seconds()),
                "user": {
                    "id": str(user.id),
                    "email": user.email,
                    "display_name": user.display_name,
                    "role": user.role,
                },
            },
            status=status.HTTP_200_OK,
        )


class CliRevokeTokenView(APIView):
    """
    Revokes an active CLI session token.
    Can be invoked by the CLI itself (with Bearer token) or web UI (passing session_id).
    """

    permission_classes = [IsAuthenticatedUser]

    def post(self, request: Request) -> Response:
        session_id = request.data.get("session_id")

        if session_id:
            # Web UI revoking a specific session belonging to user
            session = CliSession.objects.filter(
                id=session_id, user=request.user
            ).first()
            if session:
                session.is_active = False
                session.save(update_fields=["is_active", "updated_at"])
                SecurityAuditEvent.record(
                    event_type=SecurityAuditEvent.EventType.CLI_SESSION_REVOKED,
                    request=request,
                    user=request.user,
                    metadata={"session_id": str(session_id)},
                )
            return Response({"status": "revoked"}, status=status.HTTP_200_OK)

        # If called from CLI, the auth session is attached in request.auth
        if isinstance(request.auth, CliSession):
            request.auth.is_active = False
            request.auth.save(update_fields=["is_active", "updated_at"])
            SecurityAuditEvent.record(
                event_type=SecurityAuditEvent.EventType.CLI_SESSION_REVOKED,
                request=request,
                user=request.user,
                metadata={"session_id": str(request.auth.id)},
            )
            return Response({"status": "revoked"}, status=status.HTTP_200_OK)

        return Response(
            {"detail": "Session ID or active CLI bearer token required."},
            status=status.HTTP_400_BAD_REQUEST,
        )


class CliSessionsListView(APIView):
    """
    Lists active CLI sessions for the authenticated user.
    """

    permission_classes = [IsAuthenticatedUser]

    def get(self, request: Request) -> Response:
        sessions = CliSession.objects.filter(
            user=request.user,
            is_active=True,
            expires_at__gt=timezone.now(),
        ).order_by("-last_used_at")
        serializer = CliSessionSerializer(sessions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """
    Revokes Firebase user refresh tokens and records an audit log event.
    Idempotent: returns HTTP 200 regardless of whether caller is actively authenticated.
    """

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            try:
                firebase_service.revoke_refresh_tokens(user.firebase_uid)
            except Exception as exc:
                logger.warning("Could not revoke Firebase tokens: %s", str(exc))

            SecurityAuditEvent.record(
                event_type=SecurityAuditEvent.EventType.TOKEN_REVOKED,
                request=request,
                user=user,
            )

        return Response({"status": "logged_out"}, status=status.HTTP_200_OK)
