"""
URL routing for the backend.

Route trees mounted here:
  - "admin/" -> Django's built-in administration section (users, widgets...),
    see services/admin.py.
  - "accounts/" -> allauth's OAuth callbacks (Google/GitHub redirect here).
  - "_allauth/" -> allauth's headless authentication API (signup, login, email
    confirmation, session). This code is not ours; only its inclusion here and
    its configuration in settings.py belong to this project.
  - "" -> the project's own django-ninja API (see services/api.py): /about.json,
    /weather, /steam, /nasa_picture, the GitHub subscription endpoints, etc.
"""

from django.contrib import admin
from django.urls import include, path

from services.api import api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("_allauth/", include("allauth.headless.urls")),
    path("", api.urls),
]
"""The route trees described in the module docstring above."""
