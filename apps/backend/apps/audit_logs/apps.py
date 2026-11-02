"""Django application configuration for NEX Security Audit Logs."""

from django.apps import AppConfig


class AuditLogsConfig(AppConfig):
    """Configuration for security audit logging application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.audit_logs"
    label = "audit_logs"
    verbose_name = "NEX Security Audit Logs"
