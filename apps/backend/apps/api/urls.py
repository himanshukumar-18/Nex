"""
NEX Backend — API v1 URL routing.

All REST API endpoints are namespaced under /api/v1/.

This router is intentionally minimal at this phase. Endpoint groups are added
here as domain applications (accounts, projects, repositories) are implemented.

URL naming convention:
  app_name = "api_v1"
  name      = "<resource>-<action>"   e.g. "projects-list", "repositories-detail"
"""

from django.urls import include, path

app_name = "api_v1"

urlpatterns: list = [
    path("auth/", include("apps.accounts.urls", namespace="accounts")),
    path("repositories/", include("apps.repositories.urls", namespace="repositories")),
]

