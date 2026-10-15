"""Plain Django views: ``/about.json`` and the JSON API of the built-in front.

The front's API views authenticate with Django's session. They are ``csrf_exempt`` only so that a
CSRF failure is answered in the JSON error contract instead of Django's HTML page:
:func:`widget_hub.api.handle` runs the same ``CsrfViewMiddleware`` check on every unsafe request.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from . import api
from .discovery import about_document


@require_GET
def about_json(request: HttpRequest) -> JsonResponse:
    """Public discovery endpoint listing services, widgets and their params."""
    return JsonResponse(about_document(request))


def _respond(result: api.Result) -> HttpResponse:
    status, body = result
    if body is None:
        return HttpResponse(status=status)
    return JsonResponse(body, status=status, safe=False)


def _run(request: HttpRequest, action: str, operation: Callable[[Any], api.Result]) -> HttpResponse:
    return _respond(api.handle(request, action, operation))


@require_GET
def catalog(request: HttpRequest) -> HttpResponse:
    """Every registered widget's schema."""
    return _run(request, "catalog", api.catalog)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def instances(request: HttpRequest) -> HttpResponse:
    """List (GET) or create (POST) the current user's instances."""
    if request.method == "POST":
        return _run(
            request, "create", lambda o: api.create_instance(o, api.parse_json_body(request.body))
        )
    return _run(request, "list", api.list_instances)


@csrf_exempt
@require_http_methods(["GET", "PATCH", "DELETE"])
def instance_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Retrieve (GET), update (PATCH) or delete (DELETE) one of the current user's instances."""
    if request.method == "PATCH":
        return _run(
            request,
            "update",
            lambda o: api.update_instance(o, pk, api.parse_json_body(request.body)),
        )
    if request.method == "DELETE":
        return _run(request, "delete", lambda o: api.delete_instance(o, pk))
    return _run(request, "retrieve", lambda o: api.retrieve_instance(o, pk))


@require_GET
def instance_data(request: HttpRequest, pk: int) -> HttpResponse:
    """The instance's widget data."""
    return _run(request, "fetch", lambda o: api.fetch_data(o, pk))


@require_GET
def credential_list(request: HttpRequest) -> HttpResponse:
    """Services the current user stored a credential for."""
    return _run(request, "credentials", api.list_credentials)


@csrf_exempt
@require_http_methods(["PUT", "DELETE"])
def credential_detail(request: HttpRequest, service: str) -> HttpResponse:
    """Store (PUT) or delete (DELETE) the current user's secret for ``service``."""
    if request.method == "PUT":
        return _run(
            request,
            "credentials",
            lambda o: api.set_credential(o, service, api.parse_json_body(request.body)),
        )
    return _run(request, "credentials", lambda o: api.delete_credential(o, service))
