"""
NEX Accounts — URL routing for authentication and CLI token endpoints.
"""

from django.urls import path

from apps.accounts.views import (
    CliAuthorizeView,
    CliRevokeTokenView,
    CliSessionsListView,
    CliTokenExchangeView,
    LogoutView,
    MeView,
    SyncProfileView,
)

app_name = "accounts"

urlpatterns = [
    path("me/", MeView.as_view(), name="me"),
    path("sync/", SyncProfileView.as_view(), name="sync"),
    path("logout/", LogoutView.as_view(), name="logout"),
    # CLI OAuth PKCE flow
    path("cli/authorize/", CliAuthorizeView.as_view(), name="cli-authorize"),
    path("cli/token/", CliTokenExchangeView.as_view(), name="cli-token"),
    path("cli/revoke/", CliRevokeTokenView.as_view(), name="cli-revoke"),
    path("cli/sessions/", CliSessionsListView.as_view(), name="cli-sessions"),
]

