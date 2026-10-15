"""Settings of widget_hub, read from the single ``WIDGET_HUB`` dict in Django settings.

Values are read on every access so ``override_settings`` works in tests. Unknown keys are
reported by the ``widget_hub.E001`` system check.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings

DEFAULTS: dict[str, Any] = {
    # Alias in settings.CACHES used for fetch() results. Django's own default cache is LocMem.
    "CACHE_ALIAS": "default",
    # Prefix of every cache key written by widget_hub.
    "CACHE_PREFIX": "widget_hub",
    # Smallest refresh rate (seconds) a user may choose for an instance.
    "MIN_REFRESH_RATE": 30,
    # Largest refresh rate (seconds) a user may choose for an instance.
    "MAX_REFRESH_RATE": 86400,
    # Wall-clock limit (seconds) for one fetch() call.
    "FETCH_TIMEOUT": 10.0,
}
"""Documented defaults; the README settings table mirrors this dict."""


def get(name: str) -> Any:
    """Return setting ``name`` from ``settings.WIDGET_HUB``, falling back to :data:`DEFAULTS`."""
    user_settings = getattr(settings, "WIDGET_HUB", {})
    return user_settings.get(name, DEFAULTS[name])
