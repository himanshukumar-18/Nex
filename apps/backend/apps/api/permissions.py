"""
NEX Backend — Authorization permission classes.

This module defines the permission architecture foundation for NEX.

Design principles:
  - Authentication and authorization are always applied independently.
  - Object-level permissions are enforced explicitly; never rely on
    queryset filtering alone to prevent unauthorized access.
  - Permission classes are named for their business intent, not their
    technical mechanism, to make authorization decisions auditable.
  - Every permission class documents its trust assumptions and failure mode.

Current permission classes:

  IsAuthenticatedUser
    Allows access only to authenticated, active users.
    Rejects anonymous requests with HTTP 401.
    Use this as the default for all authenticated API endpoints.

  AllowAny
    Imported from DRF. Allows unauthenticated access.
    Use only for fully public endpoints (health checks, public docs).
    Rate limiting MUST be applied to all AllowAny endpoints.

  IsReadOnly
    Allows GET/HEAD/OPTIONS to any caller (authenticated or not).
    Rejects write operations (POST/PUT/PATCH/DELETE) with HTTP 403.
    Use for genuinely public read-only resources.

Future permission classes (to be added in subsequent phases):
  - OrganizationMemberPermission
  - ProjectMemberPermission
  - RepositoryAccessPermission
  - AgentRunOwnerPermission
  - IsAdministrator

Note: Object-level permissions must be enforced by calling
`self.check_object_permissions(request, obj)` in view methods.
Never rely solely on queryset filtering.
"""

from typing import TYPE_CHECKING

from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request

if TYPE_CHECKING:
    from rest_framework.views import APIView


class IsAuthenticatedUser(BasePermission):
    """
    Permit access only to verified, authenticated users.

    Rejects:
      - Unauthenticated requests (HTTP 401 Authentication Required)
      - Requests from inactive user accounts (HTTP 403 Permission Denied)

    Use this as the default for all non-public endpoints.
    """

    message = "Authentication credentials are required."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active
        )


class IsReadOnly(BasePermission):
    """
    Permit safe HTTP methods (GET, HEAD, OPTIONS) to any caller.

    Write operations (POST, PUT, PATCH, DELETE) are rejected with HTTP 403.

    Use for publicly readable resources. Rate limiting should still be
    applied to prevent enumeration and scraping.
    """

    message = "This endpoint supports read-only access."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return request.method in SAFE_METHODS
