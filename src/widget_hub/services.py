"""Framework-agnostic service layer.

Every HTTP adapter (django-ninja, DRF, the built-in views) goes through these functions, so
owner scoping and validation are implemented once. All functions take the ``owner`` explicitly:
an instance belonging to someone else is reported as :class:`~widget_hub.exceptions.NotFound`,
exactly like a missing one, so ids of other users' instances cannot be probed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.db.models import QuerySet

from . import conf, credentials
from .exceptions import InvalidInput, NotFound, ParamValidationError
from .fetching import FetchResult, cached_fetch
from .models import WidgetInstance
from .registry import registry
from .widgets import Widget

UNSET: Any = object()
"""Marker for "field not supplied" in :func:`update_instance`."""

POSITION_KEYS = ("x", "y", "w", "h")
POSITION_MAX = 1000


@dataclass(frozen=True)
class FetchContext:
    """Information passed to :meth:`Widget.fetch` besides the params.

    :ivar owner: the user who owns the instance being refreshed.
    :ivar instance_id: primary key of that instance.
    :ivar credential: the owner's decrypted secret for the widget's service when the widget sets
        ``uses_credential``; ``None`` otherwise or when none is stored. Never log it.
    """

    owner: AbstractBaseUser
    instance_id: int
    credential: str | None = field(default=None, repr=False)


def serialize_instance(instance: WidgetInstance) -> dict[str, Any]:
    """Return the public JSON representation of ``instance``."""
    return {
        "id": instance.pk,
        "service": instance.service,
        "widget": instance.widget,
        "params": instance.params,
        "refresh_rate": instance.refresh_rate,
        "position": instance.position,
        "created_at": instance.created_at.isoformat(),
        "updated_at": instance.updated_at.isoformat(),
    }


def serialize_result(result: FetchResult) -> dict[str, Any]:
    """Return the public JSON representation of fetched data."""
    return {
        "data": result.data,
        "fetched_at": datetime.fromtimestamp(result.fetched_at, tz=timezone.utc).isoformat(),
        "cached": result.cached,
    }


def list_instances(owner: AbstractBaseUser) -> QuerySet[WidgetInstance]:
    """Return the owner's instances, oldest first."""
    return WidgetInstance.objects.filter(owner=owner)


def get_instance(owner: AbstractBaseUser, instance_id: Any) -> WidgetInstance:
    """Return the owner's instance ``instance_id`` or raise NotFound."""
    try:
        return WidgetInstance.objects.get(pk=int(instance_id), owner=owner)
    except (WidgetInstance.DoesNotExist, TypeError, ValueError):
        raise NotFound("Widget instance not found.") from None


def get_widget(service: str, widget: str) -> Widget:
    """Return the registered widget or raise NotFound."""
    found = registry.get(service, widget)
    if found is None:
        raise NotFound(f"Unknown widget {service}.{widget}.")
    return found


def create_instance(
    owner: AbstractBaseUser,
    *,
    service: str,
    widget: str,
    params: Any = None,
    refresh_rate: Any = None,
    position: Any = None,
) -> WidgetInstance:
    """Validate the payload and create an instance owned by ``owner``.

    ``refresh_rate`` defaults to the widget's ``default_refresh_rate`` (kept within the
    ``MIN_REFRESH_RATE``/``MAX_REFRESH_RATE`` settings); ``position`` defaults to ``{}``.
    """
    widget_obj = registry.get(service, widget)
    if widget_obj is None:
        raise InvalidInput({"widget": f"Unknown widget {service}.{widget}."})
    if refresh_rate is None:
        refresh_rate = min(
            max(widget_obj.default_refresh_rate, conf.get("MIN_REFRESH_RATE")),
            conf.get("MAX_REFRESH_RATE"),
        )
    errors: dict[str, object] = {}
    cleaned = _clean_fields(
        widget_obj,
        errors,
        params=params,
        refresh_rate=refresh_rate,
        position={} if position is None else position,
    )
    if errors:
        raise InvalidInput(errors)
    return WidgetInstance.objects.create(owner=owner, service=service, widget=widget, **cleaned)


def update_instance(
    owner: AbstractBaseUser,
    instance_id: Any,
    *,
    params: Any = UNSET,
    refresh_rate: Any = UNSET,
    position: Any = UNSET,
) -> WidgetInstance:
    """Update the supplied fields of the owner's instance; omitted fields are left unchanged."""
    instance = get_instance(owner, instance_id)
    supplied = {
        k: v
        for k, v in {"params": params, "refresh_rate": refresh_rate, "position": position}.items()
        if v is not UNSET
    }
    if not supplied:
        return instance
    widget_obj = get_widget(instance.service, instance.widget)
    errors: dict[str, object] = {}
    cleaned = _clean_fields(widget_obj, errors, **supplied)
    if errors:
        raise InvalidInput(errors)
    for name, value in cleaned.items():
        setattr(instance, name, value)
    instance.save(update_fields=[*cleaned, "updated_at"])
    return instance


def delete_instance(owner: AbstractBaseUser, instance_id: Any) -> None:
    """Delete the owner's instance or raise NotFound."""
    get_instance(owner, instance_id).delete()


def fetch_instance_data(owner: AbstractBaseUser, instance_id: Any) -> FetchResult:
    """Return the data of the owner's instance, from the cache when it is recent enough.

    The cache entry may be at most ``instance.refresh_rate`` seconds old (never less than
    ``MIN_REFRESH_RATE``), so calling this in a loop never reaches the upstream API more than
    once per refresh period.

    :raises NotFound: unknown instance or widget.
    :raises InvalidInput: the stored params no longer match the widget's declaration.
    :raises WidgetError: raised by ``fetch()``, message meant for the user.
    :raises WidgetUnavailable: ``fetch()`` crashed, timed out or returned non-JSON data.
    """
    instance = get_instance(owner, instance_id)
    widget_obj = get_widget(instance.service, instance.widget)
    try:
        params = widget_obj.validate(instance.params)
    except ParamValidationError as exc:
        raise InvalidInput({"params": exc.errors}) from None
    # Loaded here, in the request thread, so fetch() never needs the ORM in its worker thread,
    # and only for the widget's own service (least privilege).
    secret = (
        credentials.get_credential(owner, instance.service) if widget_obj.uses_credential else None
    )
    return cached_fetch(
        widget_obj,
        params,
        FetchContext(owner=owner, instance_id=instance.pk, credential=secret),
        max_age=max(instance.refresh_rate, conf.get("MIN_REFRESH_RATE")),
        owner_id=owner.pk,
    )


def _clean_fields(widget: Widget, errors: dict[str, object], **fields: Any) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    if "params" in fields:
        try:
            cleaned["params"] = widget.validate(fields["params"])
        except ParamValidationError as exc:
            errors["params"] = exc.errors
    if "refresh_rate" in fields:
        value = fields["refresh_rate"]
        minimum, maximum = conf.get("MIN_REFRESH_RATE"), conf.get("MAX_REFRESH_RATE")
        if isinstance(value, bool) or not isinstance(value, int):
            errors["refresh_rate"] = "Must be an integer number of seconds."
        elif not minimum <= value <= maximum:
            errors["refresh_rate"] = f"Must be between {minimum} and {maximum} seconds."
        else:
            cleaned["refresh_rate"] = value
    if "position" in fields:
        try:
            cleaned["position"] = conf.hook("POSITION_VALIDATOR")(fields["position"])
        except ValueError as exc:
            errors["position"] = str(exc)
    return cleaned


def clean_position(value: Any) -> dict[str, int]:
    """Validate a grid position: an object with optional integer keys x, y, w, h."""
    if not isinstance(value, dict):
        raise ValueError("Must be an object with keys x, y, w, h.")
    unknown = sorted(set(value) - set(POSITION_KEYS))
    if unknown:
        raise ValueError(f"Unknown keys: {', '.join(map(str, unknown))}.")
    minimum = {"x": 0, "y": 0, "w": 1, "h": 1}
    for key, item in value.items():
        if isinstance(item, bool) or not isinstance(item, int):
            raise ValueError(f"{key} must be an integer.")
        if not minimum[key] <= item <= POSITION_MAX:
            raise ValueError(f"{key} must be between {minimum[key]} and {POSITION_MAX}.")
    return dict(value)
