"""URLconf to include at the site root: ``path("", include("widget_hub.urls"))``."""

from django.urls import path

from . import views

app_name = "widget_hub"

urlpatterns = [
    path("about.json", views.about_json, name="about"),
]
