"""System checks validating the ``WIDGET_HUB`` setting."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.checks import Error, register

from . import conf


@register()
def check_settings(app_configs: Any = None, **kwargs: Any) -> list[Error]:
    """Report unknown keys and inconsistent values in ``settings.WIDGET_HUB``."""
    user_settings = getattr(settings, "WIDGET_HUB", {})
    if not isinstance(user_settings, dict):
        return [Error("WIDGET_HUB must be a dict.", id="widget_hub.E001")]
    errors = [
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
    if conf.get("CACHE_ALIAS") not in settings.CACHES:
        errors.append(
            Error(
                f"WIDGET_HUB CACHE_ALIAS {conf.get('CACHE_ALIAS')!r} is not defined in CACHES.",
                id="widget_hub.E004",
            )
        )
    return errors
