"""Admin registration for widget_hub models."""

from django.contrib import admin

from .models import Credential, WidgetInstance


@admin.register(WidgetInstance)
class WidgetInstanceAdmin(admin.ModelAdmin):
    """Lists widget instances; params are validated by ``WidgetInstance.clean``."""

    list_display = ("id", "owner", "service", "widget", "refresh_rate", "updated_at")
    list_filter = ("service", "widget")
    search_fields = ("service", "widget")
    list_select_related = ("owner",)
    raw_id_fields = ("owner",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Credential)
class CredentialAdmin(admin.ModelAdmin):
    """Shows which users stored a credential for which service; never the secret itself."""

    list_display = ("id", "owner", "service", "updated_at")
    list_filter = ("service",)
    list_select_related = ("owner",)
    fields = ("owner", "service", "created_at", "updated_at")
    readonly_fields = ("owner", "service", "created_at", "updated_at")

    def has_add_permission(self, request):
        """Secrets are entered by their owner through the API, never typed in the admin."""
        return False
