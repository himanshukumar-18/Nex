"""Django application configuration for NEX Core."""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Configuration for the core system application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"
    verbose_name = "NEX Core Foundation"

