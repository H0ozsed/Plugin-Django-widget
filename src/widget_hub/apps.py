"""Django application configuration for widget_hub."""

from django.apps import AppConfig


class WidgetHubConfig(AppConfig):
    """App config: registers the app under the label ``widget_hub``."""

    name = "widget_hub"
    verbose_name = "Widget Hub"
    default_auto_field = "django.db.models.BigAutoField"
