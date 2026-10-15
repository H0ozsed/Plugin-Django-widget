"""URLconf used by the test suite."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("widget_hub.urls")),
]
