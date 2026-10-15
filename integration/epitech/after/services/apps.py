"""Django app configuration for `services`, the dashboard's own application."""

from django.apps import AppConfig


class ServicesConfig(AppConfig):
    """Its ``widgets.py`` is imported by django-widget-hub at startup."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "services"
