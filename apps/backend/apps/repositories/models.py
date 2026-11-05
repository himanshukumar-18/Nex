"""NEX Repositories — GitHub Authorization & Installation Models.

Defines persistent models for tracking authorized GitHub App installations,
user associations, permission scopes, and idempotent webhook deliveries.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone as django_timezone

from apps.core.models import BaseModel


class GitHubInstallation(BaseModel):
    """Tracks an authorized GitHub App installation and its binding to a NEX user."""

    class AccountType(models.TextChoices):
        USER = "User", "User"
        ORGANIZATION = "Organization", "Organization"

    class TargetType(models.TextChoices):
        ALL = "all", "All Repositories"
        SELECTED = "selected", "Selected Repositories"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        DELETED = "deleted", "Deleted"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="github_installations",
        help_text="Authenticated NEX user who authorized this GitHub App installation.",
    )
    installation_id = models.BigIntegerField(
        unique=True,
        db_index=True,
        help_text="Authoritative numeric installation ID assigned by GitHub.",
    )
    account_login = models.CharField(
        max_length=255,
        help_text="GitHub username or organization slug owning the installation.",
    )
    account_type = models.CharField(
        max_length=32,
        choices=AccountType.choices,
        default=AccountType.USER,
        help_text="Type of GitHub account (User or Organization).",
    )
    account_avatar_url = models.URLField(
        max_length=1024,
        blank=True,
        default="",
        help_text="Avatar URL for the connected GitHub account or organization.",
    )
    target_type = models.CharField(
        max_length=32,
        choices=TargetType.choices,
        default=TargetType.SELECTED,
        help_text="Repository selection scope (all or selected).",
    )
    permissions = models.JSONField(
        default=dict,
        blank=True,
        help_text="Granted repository and organization permission scopes.",
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
        help_text="Current lifecycle state of the GitHub App installation.",
    )
    installed_at = models.DateTimeField(
        default=django_timezone.now,
        help_text="Timestamp when the installation was completed.",
    )
    last_synced_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the most recent synchronization or token refresh.",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Sanitized GitHub installation metadata (URLs, IDs, timestamps).",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "GitHub Installation"
        verbose_name_plural = "GitHub Installations"
        indexes = [
            models.Index(
                fields=["user", "status"], name="repo_install_user_status_idx"
            ),
            models.Index(
                fields=["installation_id", "status"], name="repo_install_id_status_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.account_login} (ID: {self.installation_id}) - {self.status}"

    @property
    def is_active(self) -> bool:
        """Check whether the installation is active and operational."""
        return self.status == self.Status.ACTIVE


class GitHubWebhookEvent(BaseModel):
    """Immutable record of an ingested GitHub webhook delivery for idempotency and auditing."""

    delivery_id = models.CharField(
        max_length=128,
        unique=True,
        db_index=True,
        help_text="Unique delivery UUID from X-GitHub-Delivery header for replay defense.",
    )
    event_type = models.CharField(
        max_length=64,
        db_index=True,
        help_text="GitHub event classification from X-GitHub-Event header.",
    )
    action = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Event action classification (e.g. created, deleted, suspended).",
    )
    payload = models.JSONField(
        default=dict,
        help_text="Verified webhook JSON payload.",
    )
    processed = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Flag indicating whether this event has been processed.",
    )
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when event processing completed.",
    )
    error_message = models.TextField(
        blank=True,
        default="",
        help_text="Error message if event processing encountered an exception.",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "GitHub Webhook Event"
        verbose_name_plural = "GitHub Webhook Events"
        indexes = [
            models.Index(
                fields=["event_type", "created_at"], name="repo_webhook_event_time_idx"
            ),
            models.Index(
                fields=["processed", "created_at"], name="repo_webhook_proc_time_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"Webhook [{self.event_type}:{self.action}] ({self.delivery_id}) - {'Processed' if self.processed else 'Pending'}"


class Repository(BaseModel):
    """Tracks a GitHub repository synchronized via an authorized GitHub App installation."""

    class OwnerType(models.TextChoices):
        USER = "User", "User"
        ORGANIZATION = "Organization", "Organization"

    class SyncStatus(models.TextChoices):
        SYNCED = "synced", "Synced"
        PENDING = "pending", "Pending"
        FAILED = "failed", "Failed"
        REMOVED = "removed", "Removed"

    installation = models.ForeignKey(
        GitHubInstallation,
        on_delete=models.CASCADE,
        related_name="repositories",
        help_text="GitHub App installation providing access to this repository.",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="repositories",
        help_text="Authenticated NEX user who owns/manages this repository binding.",
    )
    github_repo_id = models.BigIntegerField(
        unique=True,
        db_index=True,
        help_text="Authoritative numeric repository ID assigned by GitHub.",
    )
    name = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Repository name (e.g. 'nex-core').",
    )
    full_name = models.CharField(
        max_length=512,
        db_index=True,
        help_text="Repository full slug including owner (e.g. 'octocat/nex-core').",
    )
    owner_login = models.CharField(
        max_length=255,
        help_text="GitHub username or organization slug owning the repository.",
    )
    owner_type = models.CharField(
        max_length=32,
        choices=OwnerType.choices,
        default=OwnerType.USER,
        help_text="Type of GitHub account owning the repository (User or Organization).",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Repository description from GitHub.",
    )
    is_private = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Flag indicating whether repository is private or public.",
    )
    is_fork = models.BooleanField(
        default=False,
        help_text="Flag indicating whether repository is a fork.",
    )
    is_archived = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Flag indicating whether repository is archived on GitHub.",
    )
    default_branch = models.CharField(
        max_length=255,
        default="main",
        help_text="Default branch name (e.g. 'main' or 'master').",
    )
    language = models.CharField(
        max_length=128,
        blank=True,
        default="",
        db_index=True,
        help_text="Primary programming language detected by GitHub.",
    )
    html_url = models.URLField(
        max_length=1024,
        help_text="Web URL to view the repository on GitHub.",
    )
    clone_url = models.URLField(
        max_length=1024,
        help_text="HTTPS clone URL for the repository.",
    )
    ssh_url = models.CharField(
        max_length=1024,
        blank=True,
        default="",
        help_text="SSH clone URL for the repository.",
    )
    permissions = models.JSONField(
        default=dict,
        blank=True,
        help_text="Granted repository permissions (admin, push, pull, etc.).",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Active state in NEX (set to False when uninstalled/removed instead of deleting).",
    )
    sync_status = models.CharField(
        max_length=32,
        choices=SyncStatus.choices,
        default=SyncStatus.SYNCED,
        db_index=True,
        help_text="Repository synchronization state.",
    )
    sync_error = models.TextField(
        blank=True,
        default="",
        help_text="Error message if repository synchronization failed.",
    )
    last_synced_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the most recent synchronization.",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata from GitHub (stargazers, open issues, size, etc.).",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Repository"
        verbose_name_plural = "Repositories"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["owner", "is_active"], name="repo_owner_act_idx"),
            models.Index(fields=["installation", "is_active"], name="repo_inst_act_idx"),
            models.Index(fields=["full_name"], name="repo_fullname_idx"),
            models.Index(fields=["language"], name="repo_lang_idx"),
            models.Index(fields=["sync_status"], name="repo_sync_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.full_name} ({'private' if self.is_private else 'public'})"


class GitOperation(BaseModel):
    """Tracks a controlled Git operation executed on a developer's repository."""

    class OperationType(models.TextChoices):
        BRANCH_CREATE = "branch_create", "Branch Create"
        BRANCH_SWITCH = "branch_switch", "Branch Switch"
        STAGE = "stage", "Stage Files"
        UNSTAGE = "unstage", "Unstage Files"
        COMMIT = "commit", "Commit"
        PUSH = "push", "Push"

    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        EXECUTED = "executed", "Executed"
        FAILED = "failed", "Failed"

    class RiskLevel(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class ApprovalStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        NOT_REQUIRED = "not_required", "Not Required"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="git_operations",
        help_text="Authenticated NEX user who performed or requested this operation.",
    )
    repository = models.ForeignKey(
        Repository,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="git_operations",
        help_text="Linked NEX repository, if this operation targets an authorized remote repo.",
    )
    operation_type = models.CharField(
        max_length=32,
        choices=OperationType.choices,
        db_index=True,
        help_text="Classification of the Git operation.",
    )
    target_branch = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Target branch name involved in the operation (e.g. created, switched, pushed).",
    )
    target_remote = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Remote name (e.g. 'origin') for push operations.",
    )
    files = models.JSONField(
        default=list,
        blank=True,
        help_text="List of relative file paths affected by stage/unstage.",
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PLANNED,
        db_index=True,
        help_text="Current state of the operation.",
    )
    risk_level = models.CharField(
        max_length=16,
        choices=RiskLevel.choices,
        default=RiskLevel.MEDIUM,
        help_text="Risk classification of the operation.",
    )
    approval_status = models.CharField(
        max_length=16,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
        help_text="Approval outcome for this operation.",
    )
    commit_sha = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Commit SHA created or referenced by the operation.",
    )
    commit_message = models.TextField(
        blank=True,
        default="",
        help_text="Commit message, if operation is a commit.",
    )
    error_message = models.TextField(
        blank=True,
        default="",
        help_text="Error message if the operation failed.",
    )
    correlation_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        help_text="Correlation ID tracing this operation across CLI and backend logs.",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional sanitized operational metadata (staged count, diff metrics, etc.).",
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the operation finished execution.",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Git Operation"
        verbose_name_plural = "Git Operations"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"], name="gitop_user_time_idx"),
            models.Index(fields=["repository", "created_at"], name="gitop_repo_time_idx"),
            models.Index(fields=["operation_type", "status"], name="gitop_type_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.operation_type} ({self.status}) by {self.user} - {self.target_branch or 'N/A'}"


class PullRequest(BaseModel):
    """Tracks a GitHub Pull Request created or synchronized within NEX."""

    class State(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"
        MERGED = "merged", "Merged"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pull_requests",
        help_text="NEX user who authored or owns this pull request.",
    )
    repository = models.ForeignKey(
        Repository,
        on_delete=models.CASCADE,
        related_name="pull_requests",
        help_text="Target repository in NEX for this pull request.",
    )
    installation = models.ForeignKey(
        GitHubInstallation,
        on_delete=models.CASCADE,
        related_name="pull_requests",
        help_text="GitHub App installation authorizing access to this repository.",
    )
    github_pr_id = models.BigIntegerField(
        unique=True,
        db_index=True,
        help_text="Authoritative numeric pull request ID assigned by GitHub.",
    )
    number = models.PositiveIntegerField(
        db_index=True,
        help_text="Repository-scoped pull request number (e.g. #42).",
    )
    title = models.CharField(
        max_length=512,
        help_text="Pull request title.",
    )
    body = models.TextField(
        blank=True,
        default="",
        help_text="Pull request description / markdown body.",
    )
    base_branch = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Target base branch (e.g. 'main').",
    )
    head_branch = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Source head branch (e.g. 'feature/auth').",
    )
    html_url = models.URLField(
        max_length=1024,
        help_text="Public web URL to view the pull request on GitHub.",
    )
    state = models.CharField(
        max_length=32,
        choices=State.choices,
        default=State.OPEN,
        db_index=True,
        help_text="Current state of the pull request (open, closed, merged).",
    )
    is_draft = models.BooleanField(
        default=False,
        help_text="Flag indicating whether this pull request is in draft mode.",
    )
    merged_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the pull request was merged on GitHub.",
    )
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the pull request was closed on GitHub.",
    )
    last_synced_at = models.DateTimeField(
        default=django_timezone.now,
        help_text="Timestamp of the most recent synchronization with GitHub.",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Sanitized GitHub pull request metadata (author, assignees, diff stats).",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Pull Request"
        verbose_name_plural = "Pull Requests"
        ordering = ["-number"]
        constraints = [
            models.UniqueConstraint(
                fields=["repository", "number"],
                name="unique_repo_pr_number",
            ),
        ]
        indexes = [
            models.Index(fields=["repository", "state"], name="pr_repo_state_idx"),
            models.Index(fields=["user", "state"], name="pr_user_state_idx"),
            models.Index(fields=["repository", "base_branch"], name="pr_repo_base_idx"),
            models.Index(fields=["repository", "head_branch"], name="pr_repo_head_idx"),
        ]

    def __str__(self) -> str:
        return f"#{self.number} {self.title} ({self.repository.full_name})"




