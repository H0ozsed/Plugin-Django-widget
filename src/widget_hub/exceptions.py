"""Exceptions raised by widget_hub."""

from __future__ import annotations


class ParamValidationError(Exception):
    """Raised when submitted parameter values do not match a widget's declaration.

    :ivar errors: mapping of parameter name (or ``"__all__"``) to a human-readable message.
    """

    def __init__(self, errors: dict[str, str]) -> None:
        self.errors = errors
        super().__init__("; ".join(f"{k}: {v}" for k, v in errors.items()))


class InvalidValue(Exception):
    """Raised by :meth:`widget_hub.params.Param.clean` for one invalid value."""


class InvalidInput(Exception):
    """Raised by the service layer when a create/update payload is invalid (HTTP 400).

    :ivar errors: field name → message; ``"params"`` maps to a dict of per-parameter messages.
    """

    def __init__(self, errors: dict[str, object]) -> None:
        self.errors = errors
        super().__init__(repr(errors))


class NotFound(Exception):
    """Raised when an instance does not exist or belongs to someone else, or when a widget is
    not registered (HTTP 404). The message is safe to show to the client."""


class WidgetError(Exception):
    """Raise it from ``fetch()`` to send ``message`` to the user with HTTP ``status``.

    Use it for expected upstream failures ("City not found", "Rate limit reached"). The message
    is shown as-is, so never put secrets or raw exception text in it. Any other exception
    raised by ``fetch()`` becomes a generic 503 (see :class:`WidgetUnavailable`).

    :param message: user-facing explanation.
    :param status: HTTP status between 400 and 599 (default 502, "bad gateway").
    """

    def __init__(self, message: str, status: int = 502) -> None:
        if isinstance(status, bool) or not isinstance(status, int) or not 400 <= status <= 599:
            raise ValueError(f"WidgetError status must be an int in 400-599, got {status!r}.")
        self.message = message
        self.status = status
        super().__init__(message)


class WidgetUnavailable(Exception):
    """A ``fetch()`` crashed or timed out. The details are logged, never sent (HTTP 503)."""

    message = "This widget is temporarily unavailable."
    status = 503

    def __init__(self) -> None:
        super().__init__(self.message)
