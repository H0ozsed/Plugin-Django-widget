"""The JSON error contract shared by every HTTP adapter.

Every error response has this shape::

    {"error": {"code": "<code>", "message": "<human-readable>", "details": {...}}}

``details`` is present only for ``invalid_input``. Codes and statuses:

=================== ====== ==========================================================
code                status meaning
=================== ====== ==========================================================
invalid_input       400    payload failed validation; ``details`` maps field → message
                           (``details.params`` maps parameter → message)
not_authenticated   401    no authenticated user
permission_denied   403    the permission check refused access
not_found           404    unknown widget, or instance missing / owned by someone else
widget_error        4xx/5xx ``fetch()`` raised ``WidgetError(message, status)``
unavailable         503    ``fetch()`` crashed or timed out (details only in server logs)
=================== ====== ==========================================================
"""

from __future__ import annotations

from typing import Any

from .exceptions import InvalidInput, NotFound, WidgetError, WidgetUnavailable


def error_body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    """Build an error body following the contract above."""
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


def to_error_response(exc: Exception) -> tuple[int, dict[str, Any]] | None:
    """Map a widget_hub exception to ``(status, body)``; ``None`` for other exceptions."""
    if isinstance(exc, InvalidInput):
        return 400, error_body("invalid_input", "Invalid input.", exc.errors)
    if isinstance(exc, NotFound):
        return 404, error_body("not_found", str(exc))
    if isinstance(exc, WidgetError):
        return exc.status, error_body("widget_error", exc.message)
    if isinstance(exc, WidgetUnavailable):
        return exc.status, error_body("unavailable", exc.message)
    return None
