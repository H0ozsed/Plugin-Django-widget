"""Admin registration for widget_hub models."""

from django.contrib import admin

from .models import WidgetInstance


@admin.register(WidgetInstance)
class WidgetInstanceAdmin(admin.ModelAdmin):
    """Lists widget instances; params are validated by ``WidgetInstance.clean``."""

    list_display = ("id", "owner", "service", "widget", "refresh_rate", "updated_at")
    list_filter = ("service", "widget")
    search_fields = ("service", "widget")
    list_select_related = ("owner",)
    raw_id_fields = ("owner",)
    readonly_fields = ("created_at", "updated_at")
