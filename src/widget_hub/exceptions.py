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
