"""Plain Django views shipped with widget_hub."""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET

from .discovery import about_document


@require_GET
def about_json(request: HttpRequest) -> JsonResponse:
    """Public discovery endpoint listing services, widgets and their params."""
    return JsonResponse(about_document(request))
