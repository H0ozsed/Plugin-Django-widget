"""System checks: the ``WIDGET_HUB`` setting, and stored instances of unknown widgets."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.checks import CheckMessage, Error, Tags, Warning, register
from django.db import DatabaseError
from django.db.models import Count
from django.utils.module_loading import import_string

from . import conf


@register()
def check_settings(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    """Report unknown keys and inconsistent values in ``settings.WIDGET_HUB``."""
    user_settings = getattr(settings, "WIDGET_HUB", {})
    if not isinstance(user_settings, dict):
        return [Error("WIDGET_HUB must be a dict.", id="widget_hub.E001")]
    errors: list[CheckMessage] = [
        Error(
            f"Unknown key {key!r} in WIDGET_HUB.",
            hint=f"Valid keys: {', '.join(sorted(conf.DEFAULTS))}.",
            id="widget_hub.E001",
        )
        for key in user_settings
        if key not in conf.DEFAULTS
    ]
    minimum, maximum = conf.get("MIN_REFRESH_RATE"), conf.get("MAX_REFRESH_RATE")
    if not (isinstance(minimum, int) and isinstance(maximum, int) and 0 < minimum <= maximum):
        errors.append(
            Error(
                "WIDGET_HUB MIN_REFRESH_RATE and MAX_REFRESH_RATE must be integers with "
                "0 < MIN_REFRESH_RATE <= MAX_REFRESH_RATE.",
                id="widget_hub.E002",
            )
        )
    timeout = conf.get("FETCH_TIMEOUT")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
        errors.append(
            Error("WIDGET_HUB FETCH_TIMEOUT must be a positive number.", id="widget_hub.E003")
        )
    cap = conf.get("MAX_CONCURRENT_FETCHES")
    if isinstance(cap, bool) or not isinstance(cap, int) or cap <= 0:
        errors.append(
            Error(
                "WIDGET_HUB MAX_CONCURRENT_FETCHES must be a positive integer.",
                id="widget_hub.E005",
            )
        )
    for hook in conf.HOOKS:
        value = conf.get(hook)
        if isinstance(value, str):
            try:
                import_string(value)
            except ImportError as exc:
                errors.append(
                    Error(f"WIDGET_HUB {hook} cannot be imported: {exc}", id="widget_hub.E006")
                )
        elif value is not None and not callable(value):
            errors.append(
                Error(
                    f"WIDGET_HUB {hook} must be a dotted path or a callable.", id="widget_hub.E006"
                )
            )
    if not conf.get("CREDENTIALS_KEY"):
        errors.append(
            Warning(
                "WIDGET_HUB CREDENTIALS_KEY is not set: stored credentials are encrypted with a "
                "key derived from SECRET_KEY.",
                hint="Set a dedicated secret so rotating SECRET_KEY without keeping it in "
                "SECRET_KEY_FALLBACKS does not make stored credentials unreadable.",
                id="widget_hub.W001",
            )
        )
    if conf.get("CACHE_ALIAS") not in settings.CACHES:
        errors.append(
            Error(
                f"WIDGET_HUB CACHE_ALIAS {conf.get('CACHE_ALIAS')!r} is not defined in CACHES.",
                id="widget_hub.E004",
            )
        )
    return errors


@register(Tags.database)
def check_stored_widgets(
    app_configs: Any = None, databases: Any = None, **kwargs: Any
) -> list[CheckMessage]:
    """Warn about stored instances whose widget is no longer registered (renamed or removed).

    A database check: it runs with ``migrate`` and ``manage.py check --database default``, not
    with a plain ``check``. Such instances answer 404 until they are renamed or deleted.
    """
    from .models import WidgetInstance
    from .registry import registry

    warnings: list[CheckMessage] = []
    for alias in databases or []:
        try:
            rows = list(
                WidgetInstance.objects.using(alias)
                .values("service", "widget")
                .annotate(count=Count("id"))
                .order_by("service", "widget")
            )
        except DatabaseError:
            continue  # table not created yet (first migrate)
        for row in rows:
            if registry.get(row["service"], row["widget"]) is None:
                name = f"{row['service']}.{row['widget']}"
                warnings.append(
                    Warning(
                        f"{row['count']} widget instance(s) in database {alias!r} use {name!r}, "
                        "which is not registered.",
                        hint="If the widget was renamed, update the rows with a data migration; "
                        "if it was removed, delete them. Until then they answer 404.",
                        obj=name,
                        id="widget_hub.W002",
                    )
                )
    return warnings
