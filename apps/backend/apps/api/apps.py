"""Django application configuration for the NEX shared API infrastructure."""

from django.apps import AppConfig


class ApiConfig(AppConfig):
    """Configuration for the shared API infrastructure application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.api"
    label = "api"
    verbose_name = "NEX API Infrastructure"

