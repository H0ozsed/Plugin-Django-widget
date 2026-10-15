"""Database models of widget_hub."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .exceptions import ParamValidationError
from .registry import registry

if TYPE_CHECKING:
    from .widgets import Widget


class WidgetInstance(models.Model):
    """One configured widget placed on its owner's dashboard.

    ``service`` and ``widget`` name a registered widget; ``params`` holds the validated values.
    Two instances of the same widget are independent rows with their own params.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="widget_instances",
    )
    service = models.CharField(max_length=100)
    widget = models.CharField(max_length=100)
    params = models.JSONField(default=dict, blank=True)
    refresh_rate = models.PositiveIntegerField(help_text="Seconds between two refreshes.")
    position = models.JSONField(
        default=dict, blank=True, help_text='Grid placement, e.g. {"x": 0, "y": 0, "w": 4, "h": 2}.'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["owner", "created_at"])]
        verbose_name = "widget instance"

    def __str__(self) -> str:
        return f"{self.service}.{self.widget} #{self.pk} ({self.owner})"

    def get_widget(self) -> Widget | None:
        """Return the registered widget this instance points to, or ``None`` if it was removed."""
        return registry.get(self.service, self.widget)

    def clean(self) -> None:
        """Check that the widget exists and that ``params`` match its declaration (admin forms)."""
        widget = self.get_widget()
        if widget is None:
            raise ValidationError({"widget": f"Unknown widget {self.service}.{self.widget}."})
        try:
            self.params = widget.validate(self.params)
        except ParamValidationError as exc:
            raise ValidationError(
                {"params": [f"{k}: {v}" for k, v in exc.errors.items()]}
            ) from None
