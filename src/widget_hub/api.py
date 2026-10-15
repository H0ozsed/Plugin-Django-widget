"""HTTP-level operations shared by every adapter (django-ninja, DRF, built-in views).

Each operation returns ``(status, body)``; adapters only wrap that in their response class.
:func:`handle` resolves the owner, enforces CSRF for cookie-authenticated unsafe requests, runs
the permission check and maps widget_hub exceptions to the JSON error contract.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.http import HttpRequest

from . import services
from .auth import csrf_rejected, has_permission, resolve_owner
from .errors import error_body, to_error_response
from .exceptions import InvalidInput
from .registry import registry

Result = tuple[int, Any]
"""``(HTTP status, JSON-serialisable body or None for 204)``."""

CREATE_FIELDS = ("service", "widget", "params", "refresh_rate", "position")
UPDATE_FIELDS = ("params", "refresh_rate", "position")


def handle(
    request: HttpRequest,
    action: str,
    operation: Callable[[AbstractBaseUser], Result],
    *,
    framework_authenticated: bool = False,
) -> Result:
    """Authenticate, authorise and run ``operation(owner)``, returning ``(status, body)``.

    Adapters pass ``framework_authenticated=True`` only when one of the framework's
    authenticators accepted the request; otherwise unsafe methods must pass Django's CSRF check.
    """
    owner = resolve_owner(request)
    if owner is None:
        return 401, error_body("not_authenticated", "Authentication required.")
    if csrf_rejected(request, framework_authenticated=framework_authenticated):
        return 403, error_body("permission_denied", "CSRF verification failed.")
    if not has_permission(request, owner, action):
        return 403, error_body("permission_denied", "Permission denied.")
    try:
        return operation(owner)
    except Exception as exc:
        mapped = to_error_response(exc)
        if mapped is None:
            raise
        return mapped


def parse_json_body(raw: bytes) -> Any:
    """Decode a request body, raising InvalidInput if it is not valid JSON."""
    try:
        return json.loads(raw or b"{}")
    except (ValueError, UnicodeDecodeError):
        raise InvalidInput({"__all__": "Request body must be valid JSON."}) from None


def _fields(payload: Any, allowed: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise InvalidInput({"__all__": "Request body must be a JSON object."})
    unknown = [key for key in payload if key not in allowed]
    if unknown:
        raise InvalidInput({str(key): "Unknown field." for key in unknown})
    return dict(payload)


def catalog(owner: AbstractBaseUser) -> Result:
    """Every registered widget's schema (used to build settings forms)."""
    return 200, [widget.schema() for widget in registry]


def list_instances(owner: AbstractBaseUser) -> Result:
    """The owner's instances."""
    return 200, [services.serialize_instance(i) for i in services.list_instances(owner)]


def create_instance(owner: AbstractBaseUser, payload: Any) -> Result:
    """Create an instance from a JSON payload; ``service`` and ``widget`` are required."""
    fields = _fields(payload, CREATE_FIELDS)
    missing = {
        key: "This field is required."
        for key in ("service", "widget")
        if not isinstance(fields.get(key), str)
    }
    if missing:
        raise InvalidInput(missing)
    instance = services.create_instance(owner, **fields)
    return 201, services.serialize_instance(instance)


def retrieve_instance(owner: AbstractBaseUser, instance_id: Any) -> Result:
    """One of the owner's instances."""
    return 200, services.serialize_instance(services.get_instance(owner, instance_id))


def update_instance(owner: AbstractBaseUser, instance_id: Any, payload: Any) -> Result:
    """Partially update an instance (``params``, ``refresh_rate``, ``position``)."""
    fields = _fields(payload, UPDATE_FIELDS)
    instance = services.update_instance(owner, instance_id, **fields)
    return 200, services.serialize_instance(instance)


def delete_instance(owner: AbstractBaseUser, instance_id: Any) -> Result:
    """Delete an instance."""
    services.delete_instance(owner, instance_id)
    return 204, None


def fetch_data(owner: AbstractBaseUser, instance_id: Any) -> Result:
    """The instance's widget data (cached, see :func:`widget_hub.services.fetch_instance_data`)."""
    return 200, services.serialize_result(services.fetch_instance_data(owner, instance_id))
