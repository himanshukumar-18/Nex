"""
Django settings for NEX backend.

Environment variables are loaded from the container environment.
Never hard-code secrets. Required production variables are validated at startup.

Settings modules:
  config.settings.base        -- shared configuration (imported by all envs)
  config.settings.development -- development overrides
  config.settings.production  -- production overrides

The active settings module is selected by DJANGO_SETTINGS_MODULE.
"""

