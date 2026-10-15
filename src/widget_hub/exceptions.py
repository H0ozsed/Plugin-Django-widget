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
