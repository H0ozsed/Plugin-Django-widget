"""Django application configuration for widget_hub."""

from django.apps import AppConfig
from django.utils.module_loading import autodiscover_modules


class WidgetHubConfig(AppConfig):
    """App config: imports every installed app's ``widgets`` module at startup."""

    name = "widget_hub"
    verbose_name = "Widget Hub"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        """Autodiscover ``<app>/widgets.py`` so ``@register`` decorators run at startup."""
        autodiscover_modules("widgets")
