"""NEX Repositories — URL Routing.

Mounts endpoints for GitHub App authorization, installation management, and webhooks.
Namespaced under api_v1:repositories.
"""

from django.urls import path

from apps.repositories.views import (
    GitHubInstallCallbackView,
    GitHubInstallationDisconnectView,
    GitHubInstallationsListView,
    GitHubInstallInitView,
    GitHubStatusView,
    GitHubWebhookView,
    GitOperationListView,
    RepositoryDetailView,
    RepositoryListView,
    RepositoryPullRequestDetailView,
    RepositoryPullRequestListCreateView,
    RepositoryPullRequestPreviewView,
    RepositoryPullRequestSyncView,
    RepositoryPushTokenView,
    RepositorySyncStatusView,
    RepositorySyncView,
)

app_name = "repositories"

urlpatterns = [
    # Repository Management & Discovery
    path("", RepositoryListView.as_view(), name="repository-list"),
    path("sync/", RepositorySyncView.as_view(), name="repository-sync"),
    path("sync/status/", RepositorySyncStatusView.as_view(), name="repository-sync-status"),
    path("operations/", GitOperationListView.as_view(), name="operations-list"),
    path("<uuid:id>/", RepositoryDetailView.as_view(), name="repository-detail"),
    path("<uuid:id>/operations/", GitOperationListView.as_view(), name="repository-operations"),
    path("<uuid:id>/push-token/", RepositoryPushTokenView.as_view(), name="repository-push-token"),

    # Pull Request Integration (Phase 5)
    path("<uuid:id>/pulls/", RepositoryPullRequestListCreateView.as_view(), name="repository-pulls-list"),
    path("<uuid:id>/pulls/preview/", RepositoryPullRequestPreviewView.as_view(), name="repository-pulls-preview"),
    path("<uuid:id>/pulls/<int:number>/", RepositoryPullRequestDetailView.as_view(), name="repository-pulls-detail"),
    path("<uuid:id>/pulls/<int:number>/sync/", RepositoryPullRequestSyncView.as_view(), name="repository-pulls-sync"),

    # GitHub App Authorization & Webhooks
    path("github/status/", GitHubStatusView.as_view(), name="github-status"),
    path("github/install/", GitHubInstallInitView.as_view(), name="github-install-init"),
    path("github/callback/", GitHubInstallCallbackView.as_view(), name="github-install-callback"),
    path("github/installations/", GitHubInstallationsListView.as_view(), name="github-installations-list"),
    path(
        "github/installations/<int:installation_id>/disconnect/",
        GitHubInstallationDisconnectView.as_view(),
        name="github-installation-disconnect",
    ),
    path("github/webhook/", GitHubWebhookView.as_view(), name="github-webhook"),
]

