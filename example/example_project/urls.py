"""URLconf of the widget_hub demo project."""

from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", login_required(TemplateView.as_view(template_name="home.html")), name="home"),
    path("", include("widget_hub.urls")),
]
