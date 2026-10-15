"""Compatibility with the dashboard's existing React front and data, used by migration 0005.

The React front places widgets freely in pixels and saves ``{x, y, width, height}``, so the
project plugs :func:`pixel_position` as ``WIDGET_HUB["POSITION_VALIDATOR"]`` instead of the
built-in grid validation.
"""

from __future__ import annotations

from typing import Any

from widget_hub import conf, registry
from widget_hub.exceptions import ParamValidationError

PIXEL_KEYS = ("x", "y", "width", "height")
PIXEL_MAX = 100_000


def pixel_position(value: Any) -> dict[str, int]:
    """Validate a free-placement position: integer pixels ``x``, ``y``, ``width``, ``height``."""
    if not isinstance(value, dict):
        raise ValueError("Must be an object with keys x, y, width, height.")
    unknown = sorted(set(value) - set(PIXEL_KEYS))
    if unknown:
        raise ValueError(f"Unknown keys: {', '.join(map(str, unknown))}.")
    for key, item in value.items():
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"{key} must be a number of pixels.")
        if not 0 <= item <= PIXEL_MAX:
            raise ValueError(f"{key} must be between 0 and {PIXEL_MAX}.")
    return {key: round(item) for key, item in value.items()}


def convert_instance(
    service: str, widget: str, params: Any, refresh_rate: int, position: Any
) -> dict[str, Any] | None:
    """Return ``WidgetInstance`` field values for a legacy row, or ``None`` if it cannot be kept.

    The old front stored keys the registry never declared in ``params`` (``latitude``,
    ``longitude``, ``refresh_rate``) and nothing validated them: undeclared keys are dropped,
    then the params must pass the widget's validation. Refresh rates are brought within the
    configured limits; positions go through the configured validator (``{}`` if invalid).
    """
    declared = registry.get(service, widget)
    if declared is None:
        return None
    known = {p.name for p in declared.params}
    raw = {k: v for k, v in (params or {}).items() if k in known}
    try:
        cleaned = declared.validate(raw)
    except ParamValidationError:
        return None
    rate = min(max(int(refresh_rate), conf.get("MIN_REFRESH_RATE")), conf.get("MAX_REFRESH_RATE"))
    try:
        layout = conf.hook("POSITION_VALIDATOR")(position or {})
    except ValueError:
        layout = {}
    return {
        "service": service,
        "widget": widget,
        "params": cleaned,
        "refresh_rate": rate,
        "position": layout,
    }
