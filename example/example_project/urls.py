"""URLconf of the widget_hub demo project."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("widget_hub.urls")),
]
