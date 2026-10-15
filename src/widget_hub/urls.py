"""URLconf to include at the site root: ``path("", include("widget_hub.urls"))``.

Provides ``/about.json`` and, under ``widget-hub/api/``, the JSON API used by the built-in front
(``{% dashboard %}``), authenticated by Django's session.
"""

from django.urls import path

from . import views

app_name = "widget_hub"

urlpatterns = [
    path("about.json", views.about_json, name="about"),
    path("widget-hub/api/catalog", views.catalog, name="catalog"),
    path("widget-hub/api/instances", views.instances, name="instances"),
    path("widget-hub/api/instances/<int:pk>", views.instance_detail, name="instance"),
    path("widget-hub/api/instances/<int:pk>/data", views.instance_data, name="instance-data"),
    path("widget-hub/api/credentials", views.credential_list, name="credentials"),
    path(
        "widget-hub/api/credentials/<slug:service>",
        views.credential_detail,
        name="credential",
    ),
]
