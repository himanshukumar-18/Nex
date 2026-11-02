"""
NEX Accounts — Role-Based Access Control and Permission Classes.
"""

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class IsDeveloperOrAdmin(BasePermission):
    """Permits access only to users with developer or administrator roles."""

    message = "Developer or administrator role required."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active
            and getattr(request.user, "is_developer", False)
        )


class IsAdminRole(BasePermission):
    """Permits access only to users with the administrator role or superusers."""

    message = "Administrator role required."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active
            and getattr(request.user, "is_admin", False)
        )


class IsEmailVerified(BasePermission):
    """Permits access only to users whose email address has been verified."""

    message = "Verified email address required."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active
            and getattr(request.user, "email_verified", False)
        )

