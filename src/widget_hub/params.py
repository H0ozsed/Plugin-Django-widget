"""Typed widget parameters.

A widget declares its parameters as a list of :class:`Param` instances::

    params = [
        String("city", max_length=100),
        Integer("days", min_value=1, max_value=16, default=5),
    ]

Declaration errors (bad names, inconsistent bounds) raise
:class:`~django.core.exceptions.ImproperlyConfigured` at import time.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any, ClassVar

from django.core.exceptions import ImproperlyConfigured

NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
"""Allowed shape for service, widget and parameter names (safe in URLs and JSON keys)."""


class _Missing:
    """Sentinel type meaning "no default declared"."""

    def __repr__(self) -> str:
        return "MISSING"


MISSING: Any = _Missing()
"""Sentinel used when a parameter has no default value."""


def check_name(kind: str, name: object) -> str:
    """Return ``name`` if it is a valid identifier for ``kind``, else raise ImproperlyConfigured."""
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise ImproperlyConfigured(
            f"Invalid {kind} name {name!r}: use lowercase letters, digits and underscores, "
            "starting with a letter."
        )
    return name


class Param:
    """Base class of every parameter type.

    :param name: key of the value in the instance's ``params`` dict.
    :param required: whether a value must be supplied when no default exists.
    :param default: value used when the parameter is omitted.
    :param label: human-readable label for forms (defaults to the name).
    :param help_text: optional hint shown in forms.
    """

    type_name: ClassVar[str] = ""
    """Type identifier exposed in ``/about.json`` and the JSON schema."""

    def __init__(
        self,
        name: str,
        *,
        required: bool = True,
        default: Any = MISSING,
        label: str = "",
        help_text: str = "",
    ) -> None:
        self.name = check_name("parameter", name)
        self.required = required
        self.default = default
        self.label = label or name.replace("_", " ").capitalize()
        self.help_text = help_text
        self._check_declaration()

    @property
    def has_default(self) -> bool:
        """True if a default value was declared."""
        return self.default is not MISSING

    def _check_declaration(self) -> None:
        """Hook for subclasses to validate their own constructor arguments."""

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.name!r})"


class String(Param):
    """A text value, optionally bounded in length."""

    type_name = "string"

    def __init__(
        self,
        name: str,
        *,
        min_length: int | None = None,
        max_length: int | None = None,
        **kwargs: Any,
    ) -> None:
        self.min_length = min_length
        self.max_length = max_length
        super().__init__(name, **kwargs)

    def _check_declaration(self) -> None:
        for attr in ("min_length", "max_length"):
            value = getattr(self, attr)
            if value is not None and (not isinstance(value, int) or value < 0):
                raise ImproperlyConfigured(f"{self!r}: {attr} must be a non-negative integer.")
        if (
            self.min_length is not None
            and self.max_length is not None
            and self.min_length > self.max_length
        ):
            raise ImproperlyConfigured(f"{self!r}: min_length is greater than max_length.")


class Integer(Param):
    """A whole number, optionally bounded."""

    type_name = "integer"

    def __init__(
        self,
        name: str,
        *,
        min_value: int | None = None,
        max_value: int | None = None,
        **kwargs: Any,
    ) -> None:
        self.min_value = min_value
        self.max_value = max_value
        super().__init__(name, **kwargs)

    def _check_declaration(self) -> None:
        if (
            self.min_value is not None
            and self.max_value is not None
            and self.min_value > self.max_value
        ):
            raise ImproperlyConfigured(f"{self!r}: min_value is greater than max_value.")


class Boolean(Param):
    """A true/false flag."""

    type_name = "boolean"


class Choice(Param):
    """One value among a fixed list of strings."""

    type_name = "choice"

    def __init__(self, name: str, *, choices: Sequence[str], **kwargs: Any) -> None:
        self.choices = tuple(choices)
        super().__init__(name, **kwargs)

    def _check_declaration(self) -> None:
        if not self.choices or not all(isinstance(c, str) for c in self.choices):
            raise ImproperlyConfigured(f"{self!r}: choices must be a non-empty list of strings.")
        if len(set(self.choices)) != len(self.choices):
            raise ImproperlyConfigured(f"{self!r}: choices contain duplicates.")


class Url(String):
    """An absolute URL whose scheme is restricted (http/https by default)."""

    type_name = "url"

    def __init__(
        self, name: str, *, schemes: Sequence[str] = ("http", "https"), **kwargs: Any
    ) -> None:
        self.schemes = tuple(schemes)
        kwargs.setdefault("max_length", 2048)
        super().__init__(name, **kwargs)

    def _check_declaration(self) -> None:
        super()._check_declaration()
        if not self.schemes:
            raise ImproperlyConfigured(f"{self!r}: schemes must not be empty.")
