"""NEX Repositories — GitHub Authorization & Webhook Views.

Handles GitHub App installation initiation, secure callback validation,
installation status querying, disconnection, and signature-verified webhook ingestion.
"""

from __future__ import annotations

import datetime
import json
import logging
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils import timezone as django_timezone
from rest_framework import permissions, renderers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.api.pagination import NexPageNumberPagination
from apps.api.throttling import (
    AnonymousRateThrottle,
    AuthenticatedRateThrottle,
    LoginRateThrottle,
)
from apps.audit_logs.models import SecurityAuditEvent
from apps.repositories.models import (
    GitHubInstallation,
    GitHubWebhookEvent,
    GitOperation,
    PullRequest,
    Repository,
)
from apps.repositories.serializers import (
    GitHubInstallationSerializer,
    GitHubInstallInitResponseSerializer,
    GitHubStatusResponseSerializer,
    GitOperationCreateSerializer,
    GitOperationSerializer,
    PullRequestCreateSerializer,
    PullRequestPreviewRequestSerializer,
    PullRequestSerializer,
    PushTokenResponseSerializer,
    RepositoryDetailSerializer,
    RepositorySerializer,
    RepositorySyncRequestSerializer,
    RepositorySyncResponseSerializer,
)
from apps.repositories.services.github_app import (
    GitHubAppAuthenticationError,
    GitHubAppConfigurationError,
    GitHubAppError,
    GitHubAppService,
    GitHubInstallationNotFoundError,
)
from apps.repositories.services.pull_request import PullRequestService
from apps.repositories.services.sync import RepositorySyncService

logger = logging.getLogger(__name__)


class GitHubStatusView(APIView):
    """Inspect system-wide GitHub App availability and the active user's installations."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AuthenticatedRateThrottle]

    def get(self, request: Request) -> Response:
        """Return GitHub App configuration status and active installations."""
        is_configured = GitHubAppService.is_configured()
        app_slug = getattr(settings, "GITHUB_APP_SLUG", "nex-engineering-assistant")

        user_installations = GitHubInstallation.objects.filter(
            user=request.user,
            status=GitHubInstallation.Status.ACTIVE,
        ).order_by("-installed_at")

        serializer = GitHubInstallationSerializer(user_installations, many=True)
        response_data = {
            "configured": is_configured,
            "app_slug": app_slug,
            "connected": user_installations.exists(),
            "installations_count": user_installations.count(),
            "installations": serializer.data,
        }

        return Response(response_data, status=status.HTTP_200_OK)


class GitHubInstallInitView(APIView):
    """Initiate a secure GitHub App installation flow for the authenticated user."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [LoginRateThrottle]

    def post(self, request: Request) -> Response:
        """Generate a CSRF state token bound to the requesting user and return the install URL."""
        if not GitHubAppService.is_configured():
            return Response(
                {
                    "error": "GITHUB_APP_NOT_CONFIGURED",
                    "message": "GitHub App credentials are not configured on the backend.",
                    "detail": "Set GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY in backend environment.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        state = GitHubAppService.generate_authorization_state(str(request.user.id))
        install_url = GitHubAppService.get_installation_url(state)

        SecurityAuditEvent.record(
            SecurityAuditEvent.EventType.GITHUB_INSTALLATION_INITIATED,
            user=request.user,
            request=request,
            metadata={"state": state[:8] + "...", "app_slug": getattr(settings, "GITHUB_APP_SLUG", "")},
        )

        return Response(
            {"install_url": install_url, "state": state},
            status=status.HTTP_200_OK,
        )


class GitHubInstallCallbackView(APIView):
    """Handle callback from official GitHub App installation or setup redirect.

    GitHub redirects with query params:
    - installation_id: numeric installation ID
    - setup_action: install / update / request
    - state: CSRF state token generated in GitHubInstallInitView (present on fresh install)
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [AnonymousRateThrottle]

    def perform_content_negotiation(self, request: Request, force: bool = False) -> tuple[renderers.BaseRenderer, str]:
        """Allow browser HTML navigation requests without 406 Not Acceptable errors."""
        return (renderers.JSONRenderer(), "application/json")

    def get(self, request: Request) -> Response | HttpResponseRedirect:
        """Validate state or existing installation, verify with GitHub, and bind/update."""
        installation_id_param = request.query_params.get("installation_id")
        state_param = request.query_params.get("state")
        setup_action = request.query_params.get("setup_action", "install")
        accept_header = request.headers.get("accept", "")
        is_html_request = "text/html" in accept_header or request.query_params.get("redirect") == "true"
        frontend_url = getattr(
            settings,
            "GITHUB_APP_CALLBACK_URL",
            "http://localhost:3000/settings",
        )

        logger.info(
            "GitHub callback received: has_installation_id=%s, has_state=%s, setup_action=%s",
            bool(installation_id_param),
            bool(state_param),
            setup_action,
        )

        # 1. Parse and validate installation ID
        if not installation_id_param:
            logger.warning("GitHub callback rejected: missing installation_id parameter.")
            if is_html_request:
                return HttpResponseRedirect(f"{frontend_url}?github=error&error=MISSING_INSTALLATION_ID")
            return Response(
                {
                    "error": "MISSING_PARAMETERS",
                    "message": "Missing required callback parameter: installation_id.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            installation_id = int(installation_id_param)
        except ValueError:
            logger.warning("GitHub callback rejected: non-integer installation_id=%s", installation_id_param)
            if is_html_request:
                return HttpResponseRedirect(f"{frontend_url}?github=error&error=INVALID_INSTALLATION_ID")
            return Response(
                {
                    "error": "INVALID_INSTALLATION_ID",
                    "message": "installation_id must be a numeric integer.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Resolve user identity and ownership
        target_user = None

        if state_param:
            # Fresh install flow with single-use cryptographic state
            user_id = GitHubAppService.consume_authorization_state(state_param)
            if not user_id:
                logger.warning(
                    "GitHub callback rejected: invalid or expired state token for installation_id=%s",
                    installation_id,
                )
                if is_html_request:
                    return HttpResponseRedirect(f"{frontend_url}?github=error&error=INVALID_STATE")
                return Response(
                    {
                        "error": "INVALID_STATE",
                        "message": "Authorization state is invalid, expired, or has already been consumed.",
                        "detail": "Please initiate the GitHub App connection again.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                target_user = User.objects.get(id=user_id, is_active=True)
                logger.info(
                    "State token verified successfully: resolved user_id=%s for installation_id=%s",
                    target_user.id,
                    installation_id,
                )
            except (User.DoesNotExist, ValueError):
                logger.warning("GitHub callback rejected: resolved user_id=%s no longer exists.", user_id)
                if is_html_request:
                    return HttpResponseRedirect(f"{frontend_url}?github=error&error=USER_NOT_FOUND")
                return Response(
                    {
                        "error": "USER_NOT_FOUND",
                        "message": "The user account associated with this authorization state no longer exists.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        else:
            # Missing-state callback (e.g. GitHub "update" redirect from settings/installations)
            # NEVER bind an installation to an arbitrary user without authenticated verification!
            existing_installation = GitHubInstallation.objects.filter(
                installation_id=installation_id
            ).select_related("user").first()

            if existing_installation and existing_installation.user:
                target_user = existing_installation.user
                logger.info(
                    "Missing-state update callback for existing verified installation_id=%s bound to user_id=%s",
                    installation_id,
                    target_user.id,
                )
            else:
                logger.warning(
                    "GitHub callback rejected: missing state token for unbound installation_id=%s",
                    installation_id,
                )
                if is_html_request:
                    return HttpResponseRedirect(f"{frontend_url}?github=error&error=UNVERIFIED_INSTALLATION")
                return Response(
                    {
                        "error": "UNVERIFIED_INSTALLATION",
                        "message": "Cannot bind installation without authenticated authorization state.",
                        "detail": "Please initiate installation from NEX Settings or connect your installation.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # 3. Verify installation through GitHub API using App JWT
        logger.info("Verifying installation_id=%s against GitHub API via App JWT", installation_id)
        try:
            install_data = GitHubAppService.get_installation(installation_id)
        except GitHubInstallationNotFoundError:
            logger.warning("GitHub API reported installation_id=%s not found.", installation_id)
            if is_html_request:
                return HttpResponseRedirect(f"{frontend_url}?github=error&error=INSTALLATION_NOT_FOUND")
            return Response(
                {
                    "error": "INSTALLATION_NOT_FOUND",
                    "message": f"Installation {installation_id} was not found on GitHub.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except GitHubAppAuthenticationError as exc:
            logger.error("GitHub App authentication failed during callback verification: %s", exc)
            if is_html_request:
                return HttpResponseRedirect(f"{frontend_url}?github=error&error=GITHUB_AUTH_FAILED")
            return Response(
                {
                    "error": "GITHUB_AUTH_FAILED",
                    "message": "Backend failed to authenticate with GitHub API.",
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except GitHubAppError as exc:
            logger.error("GitHub API error during callback: %s", exc)
            if is_html_request:
                return HttpResponseRedirect(f"{frontend_url}?github=error&error=GITHUB_API_ERROR")
            return Response(
                {
                    "error": "GITHUB_API_ERROR",
                    "message": str(exc),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # 4. Extract account and permission metadata
        account_info = install_data.get("account", {})
        account_login = account_info.get("login", "")
        account_type = account_info.get("type", "User")
        account_avatar = account_info.get("avatar_url", "")
        target_type = install_data.get("target_type", "selected")
        permissions_dict = install_data.get("permissions", {})

        # 5. Transaction-safe record update or creation
        with transaction.atomic():
            installation, created = GitHubInstallation.objects.update_or_create(
                installation_id=installation_id,
                defaults={
                    "user": target_user,
                    "account_login": account_login,
                    "account_type": account_type,
                    "account_avatar_url": account_avatar,
                    "target_type": target_type,
                    "permissions": permissions_dict,
                    "status": GitHubInstallation.Status.ACTIVE,
                    "installed_at": django_timezone.now(),
                    "last_synced_at": django_timezone.now(),
                    "metadata": install_data,
                },
            )

        logger.info(
            "GitHub installation %s (%s) persisted in DB for user_id=%s (created=%s)",
            installation_id,
            account_login,
            target_user.id,
            created,
        )

        # Invalidate any stale token in cache
        GitHubAppService.revoke_cached_token(installation_id)

        # 6. Trigger initial repository discovery in a safe non-fatal block
        sync_success = True
        try:
            RepositorySyncService.sync_installation_repositories(installation)
            logger.info("Initial repository sync succeeded for installation_id=%s", installation_id)
        except Exception as sync_exc:
            sync_success = False
            logger.warning(
                "Initial repository sync encountered an issue for installation %s: %s",
                installation_id,
                sync_exc,
            )

        # 7. Audit logging
        SecurityAuditEvent.record(
            SecurityAuditEvent.EventType.GITHUB_INSTALLATION_COMPLETED,
            user=target_user,
            request=request,
            metadata={
                "installation_id": installation_id,
                "account_login": account_login,
                "account_type": account_type,
                "setup_action": setup_action,
                "created": created,
                "repository_sync": "completed" if sync_success else "failed",
            },
        )

        logger.info(
            "Successfully associated GitHub installation %s (%s) with user %s (sync=%s).",
            installation_id,
            account_login,
            target_user.email,
            "completed" if sync_success else "failed",
        )

        # 8. Redirect browser to frontend settings page if HTML requested, else JSON
        if is_html_request:
            redirect_action = "updated" if setup_action == "update" and not created else "connected"
            redirect_target = f"{frontend_url}?github={redirect_action}&installation_id={installation_id}"
            if not sync_success:
                redirect_target += "&sync=failed"
            logger.info("Redirecting browser to frontend settings URL: %s", frontend_url)
            return HttpResponseRedirect(redirect_target)

        return Response(
            {
                "status": "connected",
                "installation": GitHubInstallationSerializer(installation).data,
                "repository_sync": "completed" if sync_success else "failed",
            },
            status=status.HTTP_200_OK,
        )


class GitHubInstallationsListView(APIView):
    """List all authorized GitHub installations belonging to the current user."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AuthenticatedRateThrottle]

    def get(self, request: Request) -> Response:
        """List active installations."""
        installations = GitHubInstallation.objects.filter(
            user=request.user,
            status=GitHubInstallation.Status.ACTIVE,
        ).order_by("-installed_at")

        serializer = GitHubInstallationSerializer(installations, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class GitHubInstallationDisconnectView(APIView):
    """Revoke and disconnect an authorized GitHub App installation."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AuthenticatedRateThrottle]

    def post(self, request: Request, installation_id: int) -> Response:
        """Mark installation status as deleted and invalidate cached access tokens."""
        installation = get_object_or_404(
            GitHubInstallation,
            installation_id=installation_id,
            user=request.user,
        )

        installation.status = GitHubInstallation.Status.DELETED
        installation.save(update_fields=["status", "updated_at"])

        GitHubAppService.revoke_cached_token(installation_id)

        SecurityAuditEvent.record(
            SecurityAuditEvent.EventType.GITHUB_INSTALLATION_DISCONNECTED,
            user=request.user,
            request=request,
            metadata={
                "installation_id": installation_id,
                "account_login": installation.account_login,
            },
        )

        return Response(
            {
                "status": "disconnected",
                "installation_id": installation_id,
                "account_login": installation.account_login,
            },
            status=status.HTTP_200_OK,
        )


class GitHubWebhookView(APIView):
    """Ingest and verify asynchronous GitHub App webhook deliveries."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [AnonymousRateThrottle]

    def perform_content_negotiation(self, request: Request, force: bool = False) -> tuple[renderers.BaseRenderer, str]:
        """Allow browser HTML navigation requests without 406 Not Acceptable errors."""
        return (renderers.JSONRenderer(), "application/json")

    def post(self, request: Request) -> Response:
        """Verify HMAC-SHA256 signature, deduplicate delivery, and process lifecycle events."""
        raw_body = request.body
        signature = request.headers.get("X-Hub-Signature-256")
        delivery_id = request.headers.get("X-GitHub-Delivery")
        event_type = request.headers.get("X-GitHub-Event")

        if not delivery_id or not event_type:
            return Response(
                {"error": "Missing required GitHub webhook headers (X-GitHub-Delivery, X-GitHub-Event)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 1. Signature verification
        if not GitHubAppService.verify_webhook_signature(raw_body, signature):
            logger.warning("Rejected webhook delivery %s due to invalid signature.", delivery_id)
            return Response(
                {"error": "Invalid webhook signature."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return Response(
                {"error": "Malformed JSON payload."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        action = payload.get("action", "")

        # 2. Replay & deduplication tracking
        with transaction.atomic():
            event_record, created = GitHubWebhookEvent.objects.get_or_create(
                delivery_id=delivery_id,
                defaults={
                    "event_type": event_type,
                    "action": action,
                    "payload": payload,
                    "processed": False,
                },
            )

        if not created and event_record.processed:
            return Response({"status": "already_processed"}, status=status.HTTP_200_OK)

        # 3. Process installation lifecycle events
        try:
            if event_type == "installation":
                install_payload = payload.get("installation", {})
                inst_id = install_payload.get("id")
                if inst_id:
                    if action == "deleted":
                        GitHubInstallation.objects.filter(installation_id=inst_id).update(
                            status=GitHubInstallation.Status.DELETED,
                            updated_at=django_timezone.now(),
                        )
                        GitHubAppService.revoke_cached_token(inst_id)
                    elif action == "suspend":
                        GitHubInstallation.objects.filter(installation_id=inst_id).update(
                            status=GitHubInstallation.Status.SUSPENDED,
                            updated_at=django_timezone.now(),
                        )
                        GitHubAppService.revoke_cached_token(inst_id)
                    elif action == "unsuspend":
                        GitHubInstallation.objects.filter(installation_id=inst_id).update(
                            status=GitHubInstallation.Status.ACTIVE,
                            updated_at=django_timezone.now(),
                        )

            elif event_type == "installation_repositories":
                install_payload = payload.get("installation", {})
                inst_id = install_payload.get("id")
                if inst_id:
                    GitHubInstallation.objects.filter(installation_id=inst_id).update(
                        last_synced_at=django_timezone.now(),
                    )
                    GitHubAppService.revoke_cached_token(inst_id)

                    # Mark removed repositories
                    removed_repos = payload.get("repositories_removed", [])
                    if removed_repos:
                        removed_ids = [r["id"] for r in removed_repos if "id" in r]
                        Repository.objects.filter(github_repo_id__in=removed_ids).update(
                            is_active=False,
                            sync_status=Repository.SyncStatus.REMOVED,
                            last_synced_at=django_timezone.now(),
                            updated_at=django_timezone.now(),
                        )

                    # Sync added repositories
                    added_repos = payload.get("repositories_added", [])
                    if added_repos:
                        inst = GitHubInstallation.objects.filter(installation_id=inst_id).first()
                        if inst and inst.is_active:
                            try:
                                RepositorySyncService.sync_installation_repositories(inst)
                            except Exception as sync_exc:
                                logger.warning(
                                    "Webhook sync failed for installation %s: %s",
                                    inst_id,
                                    sync_exc,
                                )

            elif event_type == "repository":
                repo_payload = payload.get("repository", {})
                repo_id = repo_payload.get("id")
                if repo_id:
                    if action == "deleted":
                        Repository.objects.filter(github_repo_id=repo_id).update(
                            is_active=False,
                            sync_status=Repository.SyncStatus.REMOVED,
                            last_synced_at=django_timezone.now(),
                            updated_at=django_timezone.now(),
                        )
                    elif action == "archived":
                        Repository.objects.filter(github_repo_id=repo_id).update(
                            is_archived=True,
                            updated_at=django_timezone.now(),
                        )
                    elif action == "unarchived":
                        Repository.objects.filter(github_repo_id=repo_id).update(
                            is_archived=False,
                            updated_at=django_timezone.now(),
                        )
                    elif action == "renamed":
                        new_name = repo_payload.get("name", "")
                        new_full_name = repo_payload.get("full_name", "")
                        Repository.objects.filter(github_repo_id=repo_id).update(
                            name=new_name,
                            full_name=new_full_name,
                            updated_at=django_timezone.now(),
                        )
                    elif action == "edited":
                        desc = repo_payload.get("description") or ""
                        branch = repo_payload.get("default_branch") or "main"
                        Repository.objects.filter(github_repo_id=repo_id).update(
                            description=desc,
                            default_branch=branch,
                            updated_at=django_timezone.now(),
                        )
                    elif action == "privatized":
                        Repository.objects.filter(github_repo_id=repo_id).update(
                            is_private=True,
                            updated_at=django_timezone.now(),
                        )
                    elif action == "publicized":
                        Repository.objects.filter(github_repo_id=repo_id).update(
                            is_private=False,
                            updated_at=django_timezone.now(),
                        )

            elif event_type == "pull_request":
                PullRequestService.sync_from_webhook(payload, action)

            # Mark processed
            event_record.processed = True
            event_record.processed_at = django_timezone.now()
            event_record.save(update_fields=["processed", "processed_at", "updated_at"])

            SecurityAuditEvent.record(
                SecurityAuditEvent.EventType.GITHUB_WEBHOOK_RECEIVED,
                metadata={
                    "delivery_id": delivery_id,
                    "event_type": event_type,
                    "action": action,
                },
            )

            return Response({"status": "processed"}, status=status.HTTP_200_OK)

        except Exception as exc:
            logger.exception("Error processing webhook %s: %s", delivery_id, exc)
            event_record.error_message = str(exc)
            event_record.save(update_fields=["error_message", "updated_at"])
            return Response(
                {"error": "Webhook processing failed.", "detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class RepositoryListView(APIView):
    """List synchronized GitHub repositories belonging to the authenticated user."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AuthenticatedRateThrottle]

    def get(self, request: Request) -> Response:
        """Filter and paginate user repositories."""
        qs = Repository.objects.filter(owner=request.user)

        # Status filter (default active only)
        status_filter = request.query_params.get("status", "active").strip().lower()
        if status_filter == "active":
            qs = qs.filter(is_active=True)
        elif status_filter == "removed":
            qs = qs.filter(is_active=False)
        # "all" leaves qs unfiltered by is_active

        # Search filter
        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(full_name__icontains=search)
                | Q(description__icontains=search)
            )

        # Visibility filter
        visibility = request.query_params.get("visibility", "").strip().lower()
        if visibility == "private":
            qs = qs.filter(is_private=True)
        elif visibility == "public":
            qs = qs.filter(is_private=False)

        # Language filter
        language = request.query_params.get("language", "").strip()
        if language:
            qs = qs.filter(language__iexact=language)

        # Archived filter
        archived = request.query_params.get("archived", "").strip().lower()
        if archived in ("true", "1"):
            qs = qs.filter(is_archived=True)
        elif archived in ("false", "0"):
            qs = qs.filter(is_archived=False)

        # Installation filter
        installation_id = request.query_params.get("installation_id")
        if installation_id:
            try:
                qs = qs.filter(installation__installation_id=int(installation_id))
            except ValueError:
                pass

        qs = qs.select_related("installation").order_by("-updated_at")

        paginator = NexPageNumberPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = RepositorySerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class RepositoryDetailView(APIView):
    """Retrieve full details of a single user-owned repository."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AuthenticatedRateThrottle]

    def get(self, request: Request, id: str) -> Response:
        """Return repository details, or 404 if not found or unauthorized."""
        repo = get_object_or_404(
            Repository.objects.select_related("installation"),
            id=id,
            owner=request.user,
        )
        serializer = RepositoryDetailSerializer(repo)
        return Response(serializer.data, status=status.HTTP_200_OK)


class RepositorySyncView(APIView):
    """Trigger manual repository synchronization for the authenticated user."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AuthenticatedRateThrottle]

    def post(self, request: Request) -> Response:
        """Synchronize repositories across user installations."""
        serializer = RepositorySyncRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        installation_id = serializer.validated_data.get("installation_id")
        result = RepositorySyncService.sync_user_repositories(
            user=request.user,
            installation_id=installation_id,
        )
        return Response(result, status=status.HTTP_200_OK)


class RepositorySyncStatusView(APIView):
    """Retrieve synchronization metrics for the authenticated user's repositories."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AuthenticatedRateThrottle]

    def get(self, request: Request) -> Response:
        """Return counts and timestamps for user repositories."""
        installations_count = request.user.github_installations.filter(
            status=GitHubInstallation.Status.ACTIVE
        ).count()
        repo_qs = Repository.objects.filter(owner=request.user, is_active=True)
        total_repos = repo_qs.count()
        public_count = repo_qs.filter(is_private=False).count()
        private_count = repo_qs.filter(is_private=True).count()
        latest_repo = repo_qs.order_by("-last_synced_at").first()

        data = {
            "installations_count": installations_count,
            "total_repositories": total_repos,
            "public_repositories": public_count,
            "private_repositories": private_count,
            "last_synced_at": (
                latest_repo.last_synced_at.isoformat()
                if latest_repo and latest_repo.last_synced_at
                else None
            ),
        }
        return Response(data, status=status.HTTP_200_OK)


class GitOperationListView(APIView):
    """List or record Git operation audit events."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AuthenticatedRateThrottle]

    def get(self, request: Request, id: str | None = None) -> Response:
        """List Git operations for a specific repository or across all user operations."""
        qs = GitOperation.objects.filter(user=request.user)
        if id:
            repo = get_object_or_404(Repository, id=id, owner=request.user)
            qs = qs.filter(repository=repo)

        op_type = request.query_params.get("type", "").strip()
        if op_type:
            qs = qs.filter(operation_type=op_type)

        op_status = request.query_params.get("status", "").strip()
        if op_status:
            qs = qs.filter(status=op_status)

        qs = qs.order_by("-created_at")
        paginator = NexPageNumberPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = GitOperationSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request: Request, id: str | None = None) -> Response:
        """Record an operation result or plan initiated by CLI or web client."""
        data = request.data.copy()
        if id and not data.get("repository_id"):
            data["repository_id"] = str(id)

        serializer = GitOperationCreateSerializer(
            data=data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        operation = serializer.save()
        return Response(
            GitOperationSerializer(operation).data,
            status=status.HTTP_201_CREATED,
        )


class RepositoryPushTokenView(APIView):
    """Issue a short-lived GitHub installation token for pushing to an authorized repository."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AuthenticatedRateThrottle]

    def post(self, request: Request, id: str) -> Response:
        """Mint a short-lived token with contents:write permission for git push."""
        repo = get_object_or_404(Repository, id=id, owner=request.user)

        if not repo.installation or not repo.installation.is_active:
            return Response(
                {
                    "error": "INSTALLATION_INACTIVE",
                    "message": "GitHub App installation is not active for this repository.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not repo.is_active or repo.is_archived:
            return Response(
                {
                    "error": "REPOSITORY_INACCESSIBLE",
                    "message": "Repository is archived or inactive in NEX.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = GitHubAppService.get_installation_access_token(
                repo.installation.installation_id,
                permissions={"contents": "write"},
                force_refresh=True,
            )
        except Exception as exc:
            logger.exception("Failed to generate push token for repo %s: %s", repo.full_name, exc)
            return Response(
                {
                    "error": "TOKEN_GENERATION_FAILED",
                    "message": f"Failed to mint GitHub push token: {exc}",
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        now = django_timezone.now()
        expires_at = now + datetime.timedelta(hours=1)

        SecurityAuditEvent.record(
            SecurityAuditEvent.EventType.GITHUB_TOKEN_GENERATED,
            user=request.user,
            request=request,
            metadata={
                "repository": repo.full_name,
                "installation_id": repo.installation.installation_id,
                "scope": "contents:write",
            },
        )

        response_data = {
            "token": token,
            "expires_at": expires_at.isoformat(),
            "repository": repo.full_name,
        }
        return Response(response_data, status=status.HTTP_200_OK)


class RepositoryPullRequestPreviewView(APIView):
    """Preview Pull Request changes and generate cryptographic approval fingerprint."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AuthenticatedRateThrottle]

    def post(self, request: Request, id: str) -> Response:
        """Preview commit and file changes between base and head branches."""
        repo = get_object_or_404(Repository, id=id, owner=request.user)
        serializer = PullRequestPreviewRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        head_branch = serializer.validated_data["head"]
        base_branch = serializer.validated_data.get("base")

        correlation_id = getattr(request, "correlation_id", "no-correlation-id")
        preview_data = PullRequestService.preview_pull_request(
            user=request.user,
            repository=repo,
            head_branch=head_branch,
            base_branch=base_branch,
            correlation_id=correlation_id,
        )
        return Response(preview_data, status=status.HTTP_200_OK)


class RepositoryPullRequestListCreateView(APIView):
    """List Pull Requests or publish an approved Pull Request for a repository."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AuthenticatedRateThrottle]

    def get(self, request: Request, id: str) -> Response:
        """List pull requests for this repository with optional state filter."""
        repo = get_object_or_404(Repository, id=id, owner=request.user)
        qs = PullRequest.objects.filter(repository=repo)

        state_filter = request.query_params.get("state", "").strip().lower()
        if state_filter in ("open", "closed", "merged"):
            qs = qs.filter(state=state_filter)

        paginator = NexPageNumberPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = PullRequestSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request: Request, id: str) -> Response:
        """Publish a developer-approved Pull Request to GitHub."""
        repo = get_object_or_404(Repository, id=id, owner=request.user)
        serializer = PullRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        correlation_id = getattr(request, "correlation_id", "no-correlation-id")
        ip_addr = request.META.get("REMOTE_ADDR")

        pr_record = PullRequestService.create_pull_request(
            user=request.user,
            repository=repo,
            title=serializer.validated_data["title"],
            head_branch=serializer.validated_data["head"],
            base_branch=serializer.validated_data.get("base") or repo.default_branch,
            body=serializer.validated_data.get("body", ""),
            draft=serializer.validated_data.get("draft", False),
            preview_fingerprint=serializer.validated_data.get("preview_fingerprint"),
            approved=serializer.validated_data["approved"],
            correlation_id=correlation_id,
            ip_address=ip_addr,
        )
        return Response(
            PullRequestSerializer(pr_record).data,
            status=status.HTTP_201_CREATED,
        )


class RepositoryPullRequestDetailView(APIView):
    """Retrieve details for a specific repository Pull Request."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AuthenticatedRateThrottle]

    def get(self, request: Request, id: str, number: int) -> Response:
        """Get Pull Request by repository ID and PR number."""
        repo = get_object_or_404(Repository, id=id, owner=request.user)
        pr_record = get_object_or_404(PullRequest, repository=repo, number=number)
        return Response(PullRequestSerializer(pr_record).data, status=status.HTTP_200_OK)


class RepositoryPullRequestSyncView(APIView):
    """Synchronize live Pull Request state from GitHub API."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AuthenticatedRateThrottle]

    def post(self, request: Request, id: str, number: int) -> Response:
        """Fetch latest PR state from GitHub and update local record."""
        repo = get_object_or_404(Repository, id=id, owner=request.user)
        correlation_id = getattr(request, "correlation_id", "no-correlation-id")
        ip_addr = request.META.get("REMOTE_ADDR")

        pr_record = PullRequestService.sync_pull_request(
            user=request.user,
            repository=repo,
            number=number,
            correlation_id=correlation_id,
            ip_address=ip_addr,
        )
        return Response(PullRequestSerializer(pr_record).data, status=status.HTTP_200_OK)




