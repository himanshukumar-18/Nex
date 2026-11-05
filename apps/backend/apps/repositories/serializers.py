"""NEX Repositories — Serializers for GitHub Authorization & Installations."""

from rest_framework import serializers

from apps.repositories.models import (
    GitHubInstallation,
    GitOperation,
    PullRequest,
    Repository,
)


class GitHubInstallationSerializer(serializers.ModelSerializer[GitHubInstallation]):
    """Serializer for public presentation of an authorized GitHub App installation."""

    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = GitHubInstallation
        fields = [
            "id",
            "installation_id",
            "account_login",
            "account_type",
            "account_avatar_url",
            "target_type",
            "permissions",
            "status",
            "is_active",
            "installed_at",
            "last_synced_at",
        ]
        read_only_fields = fields


class GitHubInstallInitResponseSerializer(serializers.Serializer):
    """Response payload for GitHub installation initiation."""

    install_url = serializers.URLField(help_text="Redirect URL to official GitHub App installation.")
    state = serializers.CharField(help_text="Cryptographic state token for CSRF & binding protection.")


class GitHubStatusResponseSerializer(serializers.Serializer):
    """System and user-level GitHub integration status."""

    configured = serializers.BooleanField(help_text="Whether backend GitHub App credentials are set.")
    app_slug = serializers.CharField(help_text="Configured GitHub App slug identifier.")
    connected = serializers.BooleanField(help_text="Whether user has at least one active installation.")
    installations_count = serializers.IntegerField(help_text="Number of active installations.")
    installations = GitHubInstallationSerializer(many=True, help_text="Active user installations.")


class RepositorySerializer(serializers.ModelSerializer[Repository]):
    """Serializer for repository listing and summary representations."""

    installation_id = serializers.IntegerField(source="installation.installation_id", read_only=True)

    class Meta:
        model = Repository
        fields = [
            "id",
            "github_repo_id",
            "installation_id",
            "name",
            "full_name",
            "owner_login",
            "owner_type",
            "description",
            "is_private",
            "is_fork",
            "is_archived",
            "default_branch",
            "language",
            "html_url",
            "is_active",
            "sync_status",
            "last_synced_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class RepositoryDetailSerializer(serializers.ModelSerializer[Repository]):
    """Detailed serializer for individual repository inspection."""

    installation = GitHubInstallationSerializer(read_only=True)

    class Meta:
        model = Repository
        fields = [
            "id",
            "github_repo_id",
            "installation",
            "name",
            "full_name",
            "owner_login",
            "owner_type",
            "description",
            "is_private",
            "is_fork",
            "is_archived",
            "default_branch",
            "language",
            "html_url",
            "clone_url",
            "ssh_url",
            "permissions",
            "is_active",
            "sync_status",
            "sync_error",
            "last_synced_at",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class RepositorySyncRequestSerializer(serializers.Serializer):
    """Optional payload for requesting repository synchronization."""

    installation_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Optional specific GitHub installation ID to synchronize.",
    )


class RepositorySyncResponseSerializer(serializers.Serializer):
    """Response payload for repository synchronization results."""

    status = serializers.CharField(default="completed")
    total = serializers.IntegerField()
    added = serializers.IntegerField()
    updated = serializers.IntegerField()
    removed = serializers.IntegerField()
    installations_synced = serializers.IntegerField()
    synced_at = serializers.CharField()


class GitOperationSerializer(serializers.ModelSerializer[GitOperation]):
    """Serializer for reading Git operation audit records."""

    user_email = serializers.EmailField(source="user.email", read_only=True)
    repository_full_name = serializers.CharField(
        source="repository.full_name", read_only=True, default=None
    )

    class Meta:
        model = GitOperation
        fields = [
            "id",
            "user_email",
            "repository_id",
            "repository_full_name",
            "operation_type",
            "target_branch",
            "target_remote",
            "files",
            "status",
            "risk_level",
            "approval_status",
            "commit_sha",
            "commit_message",
            "error_message",
            "correlation_id",
            "metadata",
            "created_at",
            "completed_at",
        ]
        read_only_fields = fields


class GitOperationCreateSerializer(serializers.ModelSerializer[GitOperation]):
    """Serializer for recording a Git operation event from CLI."""

    repository_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = GitOperation
        fields = [
            "repository_id",
            "operation_type",
            "target_branch",
            "target_remote",
            "files",
            "status",
            "risk_level",
            "approval_status",
            "commit_sha",
            "commit_message",
            "error_message",
            "metadata",
        ]

    def create(self, validated_data: dict) -> GitOperation:
        user = self.context["request"].user
        repo_id = validated_data.pop("repository_id", None)
        repo = None
        if repo_id:
            repo = Repository.objects.filter(id=repo_id, owner=user).first()

        correlation_id = getattr(self.context["request"], "correlation_id", "")
        return GitOperation.objects.create(
            user=user,
            repository=repo,
            correlation_id=correlation_id,
            **validated_data,
        )


class PushTokenResponseSerializer(serializers.Serializer):
    """Response payload containing a short-lived push token."""

    token = serializers.CharField(help_text="Short-lived GitHub installation access token.")
    expires_at = serializers.DateTimeField(help_text="Token expiration timestamp.")
    repository = serializers.CharField(help_text="Target repository full slug.")


class PullRequestSerializer(serializers.ModelSerializer[PullRequest]):
    """Serializer for displaying persistent Pull Request records."""

    repository_full_name = serializers.CharField(source="repository.full_name", read_only=True)
    author_username = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = PullRequest
        fields = [
            "id",
            "repository",
            "repository_full_name",
            "author_username",
            "github_pr_id",
            "number",
            "title",
            "body",
            "base_branch",
            "head_branch",
            "html_url",
            "state",
            "is_draft",
            "merged_at",
            "closed_at",
            "last_synced_at",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class PullRequestPreviewRequestSerializer(serializers.Serializer):
    """Input payload for previewing a Pull Request."""

    head = serializers.CharField(required=True, max_length=255, help_text="Source head branch.")
    base = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
        help_text="Target base branch (default: repository default branch).",
    )


class PullRequestCreateSerializer(serializers.Serializer):
    """Input payload for publishing a Pull Request."""

    title = serializers.CharField(required=True, max_length=512, help_text="Pull request title.")
    head = serializers.CharField(required=True, max_length=255, help_text="Source head branch.")
    base = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
        help_text="Target base branch.",
    )
    body = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text="Markdown body description.",
    )
    draft = serializers.BooleanField(required=False, default=False, help_text="Publish as draft PR.")
    preview_fingerprint = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Bound preview fingerprint from preview endpoint.",
    )
    approved = serializers.BooleanField(required=True, help_text="Explicit developer confirmation.")

    def validate_approved(self, value: bool) -> bool:
        if not value:
            raise serializers.ValidationError("PR creation requires explicit developer approval.")
        return value




