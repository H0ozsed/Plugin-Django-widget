"""Django REST framework adapter (``pip install django-widget-hub[drf]``).

Include the router's URLs; views use your ``DEFAULT_AUTHENTICATION_CLASSES``::

    from widget_hub.contrib.drf import build_router

    urlpatterns = [path("api/widgets/", include(build_router().urls))]

Routes match the django-ninja adapter: ``catalog``, ``instances``, ``instances/{id}`` and
``instances/{id}/data`` (no trailing slash by default). CSRF for session users is enforced by
DRF's ``SessionAuthentication``; when no DRF authenticator accepted the request (e.g. a custom
``OWNER_RESOLVER`` reading Django's session), widget_hub applies Django's CSRF check itself.
Bodies must be JSON; errors follow :mod:`widget_hub.errors`.
"""

from __future__ import annotations

from typing import Any

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.routers import SimpleRouter

from .. import api


def _respond(result: api.Result) -> Response:
    status, body = result
    return Response(body, status=status)


def _handle(request: Request, name: str, operation: Any) -> Response:
    request.user  # noqa: B018 - runs DRF authentication (SessionAuthentication checks CSRF)
    return _respond(
        api.handle(
            request,
            name,
            operation,
            framework_authenticated=request.successful_authenticator is not None,
        )
    )


class CatalogViewSet(viewsets.ViewSet):
    """Registered widgets and their parameter schema."""

    def list(self, request: Request) -> Response:
        """List every registered widget's schema."""
        return _handle(request, "catalog", api.catalog)


class WidgetInstanceViewSet(viewsets.ViewSet):
    """The current user's widget instances; other users' instances answer 404."""

    lookup_value_regex = r"\d+"

    def list(self, request: Request) -> Response:
        """List the current user's instances."""
        return _handle(request, "list", api.list_instances)

    def create(self, request: Request) -> Response:
        """Create an instance from ``service``, ``widget``, ``params``, ``refresh_rate``,
        ``position``."""
        return _handle(
            request,
            "create",
            lambda owner: api.create_instance(owner, api.parse_json_body(request.body)),
        )

    def retrieve(self, request: Request, pk: str) -> Response:
        """Return one instance."""
        return _handle(request, "retrieve", lambda owner: api.retrieve_instance(owner, pk))

    def partial_update(self, request: Request, pk: str) -> Response:
        """Update ``params``, ``refresh_rate`` and/or ``position``."""
        return _handle(
            request,
            "update",
            lambda owner: api.update_instance(owner, pk, api.parse_json_body(request.body)),
        )

    def destroy(self, request: Request, pk: str) -> Response:
        """Delete an instance."""
        return _handle(request, "delete", lambda owner: api.delete_instance(owner, pk))

    @action(detail=True, methods=["get"])
    def data(self, request: Request, pk: str) -> Response:
        """Return the widget's data for this instance (cached for its refresh rate)."""
        return _handle(request, "fetch", lambda owner: api.fetch_data(owner, pk))


class CredentialViewSet(viewsets.ViewSet):
    """The current user's stored credentials: list services, ``PUT``/``DELETE`` by service."""

    lookup_field = "service"
    lookup_value_regex = r"[a-z][a-z0-9_]*"

    def list(self, request: Request) -> Response:
        """List services with a stored credential (secrets are never returned)."""
        return _handle(request, "credentials", api.list_credentials)

    def update(self, request: Request, service: str) -> Response:
        """Store the secret for ``service`` from body ``{"secret": "..."}``."""
        return _handle(
            request,
            "credentials",
            lambda owner: api.set_credential(owner, service, api.parse_json_body(request.body)),
        )

    def destroy(self, request: Request, service: str) -> Response:
        """Delete the secret for ``service``."""
        return _handle(request, "credentials", lambda owner: api.delete_credential(owner, service))


def build_router(*, trailing_slash: bool = False) -> SimpleRouter:
    """Return a ``SimpleRouter`` with ``catalog``, ``instances`` and ``credentials``."""
    router = SimpleRouter(trailing_slash=trailing_slash)
    router.register("catalog", CatalogViewSet, basename="widget-hub-catalog")
    router.register("instances", WidgetInstanceViewSet, basename="widget-hub-instance")
    router.register("credentials", CredentialViewSet, basename="widget-hub-credential")
    return router
