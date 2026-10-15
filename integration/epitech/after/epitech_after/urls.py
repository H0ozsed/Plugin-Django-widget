"""URL routing of the dashboard after the migration (allauth routes omitted, unchanged)."""

from django.contrib import admin
from django.urls import include, path
from services.api import api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("widget_hub.urls")),  # /about.json (+ the built-in front's API)
    path("", api.urls),
]
