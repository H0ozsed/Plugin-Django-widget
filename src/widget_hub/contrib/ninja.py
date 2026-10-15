"""django-ninja adapter (``pip install django-widget-hub[ninja]``).

Mount the router in your own API; it inherits the API's ``auth``::

    from ninja import NinjaAPI
    from widget_hub.contrib.ninja import build_router

    api = NinjaAPI(auth=...)
    api.add_router("/widgets", build_router())

Routes (relative to the mount point): ``GET /catalog``, ``GET|POST /instances``,
``GET|PATCH|DELETE /instances/{id}``, ``GET /instances/{id}/data``. Errors follow
:mod:`widget_hub.errors`. Bodies are parsed by widget_hub, not by pydantic, so validation errors
use the same contract as every other adapter.
"""

from __future__ import annotations

from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from ninja import Router

from .. import api

_INSTANCE_BODY = {
    "requestBody": {
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "service": {"type": "string"},
                        "widget": {"type": "string"},
                        "params": {"type": "object"},
                        "refresh_rate": {"type": "integer"},
                        "position": {"type": "object"},
                    },
                }
            }
        },
        "required": True,
    }
}


def _run(request: HttpRequest, name: str, operation: Any) -> api.Result:
    # ninja sets request.auth to whatever one of the API's authenticators returned.
    authenticated = getattr(request, "auth", None) is not None
    return api.handle(request, name, operation, framework_authenticated=authenticated)


def _respond(result: api.Result) -> HttpResponse:
    status, body = result
    if body is None:
        return HttpResponse(status=status)
    return JsonResponse(body, status=status, safe=False)


def build_router(**router_kwargs: Any) -> Router:
    """Return a new ninja ``Router`` exposing widget_hub (a router can be mounted only once)."""
    router_kwargs.setdefault("tags", ["widgets"])
    router = Router(**router_kwargs)

    @router.get("/catalog", operation_id="widget_hub_catalog")
    def catalog(request: HttpRequest) -> HttpResponse:
        """List registered widgets with their parameter schema."""
        return _respond(_run(request, "catalog", api.catalog))

    @router.get("/instances", operation_id="widget_hub_list")
    def list_instances(request: HttpRequest) -> HttpResponse:
        """List the current user's widget instances."""
        return _respond(_run(request, "list", api.list_instances))

    @router.post("/instances", operation_id="widget_hub_create", openapi_extra=_INSTANCE_BODY)
    def create_instance(request: HttpRequest) -> HttpResponse:
        """Add a widget instance to the current user's dashboard."""
        return _respond(
            _run(
                request,
                "create",
                lambda owner: api.create_instance(owner, api.parse_json_body(request.body)),
            )
        )

    @router.get("/instances/{int:instance_id}", operation_id="widget_hub_retrieve")
    def retrieve_instance(request: HttpRequest, instance_id: int) -> HttpResponse:
        """Return one of the current user's instances (404 for anyone else's)."""
        return _respond(_run(request, "retrieve", lambda o: api.retrieve_instance(o, instance_id)))

    @router.patch(
        "/instances/{int:instance_id}",
        operation_id="widget_hub_update",
        openapi_extra=_INSTANCE_BODY,
    )
    def update_instance(request: HttpRequest, instance_id: int) -> HttpResponse:
        """Update params, refresh_rate and/or position of an instance."""
        return _respond(
            _run(
                request,
                "update",
                lambda o: api.update_instance(o, instance_id, api.parse_json_body(request.body)),
            )
        )

    @router.delete("/instances/{int:instance_id}", operation_id="widget_hub_delete")
    def delete_instance(request: HttpRequest, instance_id: int) -> HttpResponse:
        """Remove an instance from the dashboard."""
        return _respond(_run(request, "delete", lambda o: api.delete_instance(o, instance_id)))

    @router.get("/instances/{int:instance_id}/data", operation_id="widget_hub_data")
    def instance_data(request: HttpRequest, instance_id: int) -> HttpResponse:
        """Return the widget's data for this instance (cached for its refresh rate)."""
        return _respond(_run(request, "fetch", lambda o: api.fetch_data(o, instance_id)))

    return router
