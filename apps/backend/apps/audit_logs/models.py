"""NEX Security Audit Logs — Models.

Immutable, structured security audit events capturing authentication,
authorization, CLI sessions, and account lifecycle actions with correlation tracking.
"""

from typing import Any

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class SecurityAuditEvent(BaseModel):
    """Immutable record of an identity, authentication, or authorization event."""

    class EventType(models.TextChoices):
        AUTH_SUCCESS = "auth_success", "Authentication Success"
        AUTH_FAILURE = "auth_failure", "Authentication Failure"
        USER_PROVISIONED = "user_provisioned", "User Provisioned"
        USER_SYNCED = "user_synced", "User Synced"
        ACCOUNT_DISABLED = "account_disabled", "Account Disabled"
        CLI_LOGIN_INITIATED = "cli_login_initiated", "CLI Login Initiated"
        CLI_LOGIN_COMPLETED = "cli_login_completed", "CLI Login Completed"
        CLI_SESSION_REVOKED = "cli_session_revoked", "CLI Session Revoked"
        TOKEN_REVOKED = "token_revoked", "Token Revoked"
        PERMISSION_DENIED = "permission_denied", "Permission Denied"
        PASSWORD_RESET_REQUESTED = (
            "password_reset_requested",
            "Password Reset Requested",
        )
        GITHUB_INSTALLATION_INITIATED = (
            "github_installation_initiated",
            "GitHub Installation Initiated",
        )
        GITHUB_INSTALLATION_COMPLETED = (
            "github_installation_completed",
            "GitHub Installation Completed",
        )
        GITHUB_INSTALLATION_DISCONNECTED = (
            "github_installation_disconnected",
            "GitHub Installation Disconnected",
        )
        GITHUB_WEBHOOK_RECEIVED = (
            "github_webhook_received",
            "GitHub Webhook Received",
        )
        GITHUB_TOKEN_GENERATED = (
            "github_token_generated",
            "GitHub Token Generated",
        )
        GITHUB_REPOSITORIES_SYNCED = (
            "github_repositories_synced",
            "GitHub Repositories Synced",
        )
        GITHUB_PULL_REQUEST_CREATED = (
            "github_pull_request_created",
            "GitHub Pull Request Created",
        )
        GITHUB_PULL_REQUEST_SYNCED = (
            "github_pull_request_synced",
            "GitHub Pull Request Synced",
        )

    event_type = models.CharField(
        max_length=64,
        choices=EventType.choices,
        db_index=True,
        help_text="Categorized classification of the security event.",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="security_audit_events",
        help_text="User associated with the event (null if unauthenticated).",
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Client IP address resolved from trusted proxy headers.",
    )
    user_agent = models.CharField(
        max_length=512,
        blank=True,
        default="",
        help_text="Client User-Agent header string.",
    )
    correlation_id = models.CharField(
        max_length=64,
        db_index=True,
        help_text="Correlation identifier tying the event to distributed request logs.",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Sanitized non-sensitive contextual metadata.",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Security Audit Event"
        verbose_name_plural = "Security Audit Events"
        indexes = [
            models.Index(
                fields=["event_type", "created_at"], name="audit_event_type_time_idx"
            ),
            models.Index(fields=["user", "created_at"], name="audit_user_time_idx"),
        ]

    def __str__(self) -> str:
        user_label = self.user.email if self.user else "Anonymous"
        return f"[{self.created_at}] {self.event_type} - {user_label} ({self.correlation_id})"

    @classmethod
    def record(
        cls,
        event_type: str,
        *,
        user: Any = None,
        request: Any = None,
        correlation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "SecurityAuditEvent":
        """Convenience factory to safely record a security audit event."""
        ip = None
        ua = ""
        cid = correlation_id or "system-event"

        if request is not None:
            # Resolve real IP using trusted proxy settings if available
            ip = getattr(request, "_client_ip", None) or request.META.get("REMOTE_ADDR")
            ua = request.META.get("HTTP_USER_AGENT", "")[:512]
            if not correlation_id and hasattr(request, "correlation_id"):
                cid = request.correlation_id

        # Scrub metadata to guarantee zero tokens or passwords leak into DB
        sanitized_meta: dict[str, Any] = {}
        if metadata:
            for k, v in metadata.items():
                lower_k = k.lower()
                if any(
                    secret in lower_k
                    for secret in (
                        "token",
                        "secret",
                        "password",
                        "key",
                        "code",
                        "verifier",
                    )
                ):
                    continue
                sanitized_meta[k] = v

        return cls.objects.create(
            event_type=event_type,
            user=user if (user and getattr(user, "is_authenticated", False)) else None,
            ip_address=ip,
            user_agent=ua,
            correlation_id=cid,
            metadata=sanitized_meta,
        )
