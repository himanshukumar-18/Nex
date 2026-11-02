"""Django application configuration for NEX Accounts and Identity."""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Configuration for accounts and identity application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    label = "accounts"
    verbose_name = "NEX Accounts & Identity"
