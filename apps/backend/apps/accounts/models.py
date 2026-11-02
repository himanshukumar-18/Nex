"""NEX Accounts — User and CLI Session Models.

Authoritative identity, role management, and PKCE CLI authentication models.
Firebase Authentication acts as the Identity Provider; Django maintains the
authoritative local user record, permissions, and session lifecycles.
"""

from typing import Any

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.utils import timezone as django_timezone

from apps.core.models import BaseModel


class UserManager(BaseUserManager["User"]):
    """Custom manager for NEX User accounts mapped to external Firebase identities."""

    def create_user(
        self,
        email: str,
        firebase_uid: str,
        password: str | None = None,
        **extra_fields: Any,
    ) -> "User":
        """Create and persist a standard User instance."""
        if not email:
            raise ValueError("An email address is required to create a user.")
        if not firebase_uid:
            raise ValueError("A Firebase UID is required to create a user.")

        email = self.normalize_email(email).lower()
        user = self.model(email=email, firebase_uid=firebase_uid, **extra_fields)

        # Firebase manages passwords; password in Django is set to unusable
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        email: str,
        firebase_uid: str,
        password: str | None = None,
        **extra_fields: Any,
    ) -> "User":
        """Create and persist a superuser instance."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMIN)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, firebase_uid, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, BaseModel):
    """Authoritative NEX user account associated with an external Firebase UID."""

    class Role(models.TextChoices):
        MEMBER = "member", "Member"
        DEVELOPER = "developer", "Developer"
        ADMIN = "admin", "Administrator"

    firebase_uid = models.CharField(
        max_length=128,
        unique=True,
        db_index=True,
        help_text="Primary external identity reference (Firebase UID).",
    )
    email = models.EmailField(
        unique=True,
        db_index=True,
        help_text="Primary email address verified by Firebase.",
    )
    email_verified = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Indicates whether the email address has been verified.",
    )
    display_name = models.CharField(max_length=255, blank=True, default="")
    avatar_url = models.URLField(max_length=1024, blank=True, default="")

    role = models.CharField(
        max_length=32,
        choices=Role.choices,
        default=Role.MEMBER,
        db_index=True,
        help_text="Application role governing access permissions.",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Inactive users are rejected by all authentication backends.",
    )
    is_staff = models.BooleanField(
        default=False,
        help_text="Controls Django admin site access.",
    )
    last_login_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of most recent successful authentication.",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Extensible identity and provider metadata.",
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["firebase_uid"]

    class Meta(BaseModel.Meta):
        verbose_name = "User"
        verbose_name_plural = "Users"
        indexes = [
            models.Index(
                fields=["email", "is_active"], name="accounts_user_email_act_idx"
            ),
            models.Index(
                fields=["firebase_uid", "is_active"], name="accounts_user_fb_act_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.email} ({self.role})"

    @property
    def is_admin(self) -> bool:
        """Check if user holds administrator role."""
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def is_developer(self) -> bool:
        """Check if user holds developer or higher role."""
        return self.role in {self.Role.DEVELOPER, self.Role.ADMIN} or self.is_superuser


class CliAuthorizationCode(BaseModel):
    """Short-lived, single-use authorization code for CLI PKCE flow."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="cli_auth_codes",
        help_text="The user authorizing the CLI connection.",
    )
    code_hash = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="SHA-256 hash of the issued authorization code.",
    )
    code_challenge = models.CharField(
        max_length=128,
        help_text="S256 PKCE code challenge provided by CLI.",
    )
    code_challenge_method = models.CharField(
        max_length=16,
        default="S256",
        help_text="PKCE challenge transformation method.",
    )
    redirect_uri = models.CharField(
        max_length=512,
        help_text="Validated loopback redirect URI.",
    )
    state = models.CharField(
        max_length=128,
        help_text="Cryptographically random OAuth state string.",
    )
    scopes = models.JSONField(
        default=list,
        blank=True,
        help_text="Authorized scopes granted to the CLI.",
    )
    is_redeemed = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Flag indicating whether code has already been consumed.",
    )
    expires_at = models.DateTimeField(
        db_index=True,
        help_text="Expiration timestamp (typically 5 minutes from creation).",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "CLI Authorization Code"
        verbose_name_plural = "CLI Authorization Codes"

    def is_valid(self) -> bool:
        """Check if authorization code is unredeemed and unexpired."""
        return not self.is_redeemed and django_timezone.now() < self.expires_at


class CliSession(BaseModel):
    """Represents an active, revocable CLI authentication session."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="cli_sessions",
        help_text="The authenticated user owning this CLI session.",
    )
    token_hash = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="SHA-256 hash of the issued CLI API session token.",
    )
    device_name = models.CharField(
        max_length=255,
        default="Terminal Client",
        help_text="Human-readable device or hostname identifier.",
    )
    last_used_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp of most recent request using this token.",
    )
    expires_at = models.DateTimeField(
        db_index=True,
        help_text="Token expiration timestamp (default: 30 days).",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Administrative or user revocation flag.",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "CLI Session"
        verbose_name_plural = "CLI Sessions"
        indexes = [
            models.Index(
                fields=["token_hash", "is_active"], name="accounts_clisess_act_idx"
            ),
        ]

    def is_valid(self) -> bool:
        """Check if session is active and not expired."""
        return self.is_active and django_timezone.now() < self.expires_at
