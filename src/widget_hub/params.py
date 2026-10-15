"""Typed widget parameters.

A widget declares its parameters as a list of :class:`Param` instances::

    params = [
        String("city", max_length=100),
        Integer("days", min_value=1, max_value=16, default=5),
    ]

Declaration errors (bad names, inconsistent bounds) raise
:class:`~django.core.exceptions.ImproperlyConfigured` at import time. Submitted values are
checked with :meth:`Param.clean`, and a whole parameter dict with :func:`validate_params`.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, ClassVar
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

from .exceptions import InvalidValue, ParamValidationError

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
    :param default: value used when the parameter is omitted (it is validated too).
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
        if self.has_default:
            try:
                self.default = self.clean(default)
            except InvalidValue as exc:
                raise ImproperlyConfigured(f"{self!r}: invalid default: {exc}") from None

    @property
    def has_default(self) -> bool:
        """True if a default value was declared."""
        return self.default is not MISSING

    def _check_declaration(self) -> None:
        """Hook for subclasses to validate their own constructor arguments."""

    def clean(self, value: Any) -> Any:
        """Return the normalised ``value`` or raise :class:`InvalidValue` with a precise message."""
        raise NotImplementedError

    def to_schema(self) -> dict[str, Any]:
        """Return a JSON-serialisable description used by forms and API clients."""
        schema: dict[str, Any] = {
            "name": self.name,
            "type": self.type_name,
            "label": self.label,
            "required": self.required and not self.has_default,
        }
        if self.has_default:
            schema["default"] = self.default
        if self.help_text:
            schema["help_text"] = self.help_text
        schema.update(self._extra_schema())
        return schema

    def _extra_schema(self) -> dict[str, Any]:
        return {}

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.name!r})"


class String(Param):
    """A text value, optionally bounded in length. Surrounding whitespace is stripped."""

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

    def clean(self, value: Any) -> str:
        if not isinstance(value, str):
            raise InvalidValue(f"Expected a string, got {type(value).__name__}.")
        value = value.strip()
        if self.min_length is not None and len(value) < self.min_length:
            raise InvalidValue(f"Must be at least {self.min_length} characters long.")
        if self.max_length is not None and len(value) > self.max_length:
            raise InvalidValue(f"Must be at most {self.max_length} characters long.")
        return value

    def _extra_schema(self) -> dict[str, Any]:
        return _bounds(min_length=self.min_length, max_length=self.max_length)


class Integer(Param):
    """A whole number, optionally bounded. Decimal strings such as ``"42"`` are accepted."""

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

    def clean(self, value: Any) -> int:
        if isinstance(value, str) and re.fullmatch(r"\s*[-+]?\d{1,18}\s*", value):
            value = int(value)
        if isinstance(value, bool) or not isinstance(value, int):
            raise InvalidValue("Expected an integer.")
        if self.min_value is not None and value < self.min_value:
            raise InvalidValue(f"Must be greater than or equal to {self.min_value}.")
        if self.max_value is not None and value > self.max_value:
            raise InvalidValue(f"Must be less than or equal to {self.max_value}.")
        return value

    def _extra_schema(self) -> dict[str, Any]:
        return _bounds(min_value=self.min_value, max_value=self.max_value)


class Boolean(Param):
    """A true/false flag. Accepts booleans and the strings true/false/1/0/yes/no/on/off."""

    type_name = "boolean"

    _TRUE = frozenset({"true", "1", "yes", "on"})
    _FALSE = frozenset({"false", "0", "no", "off"})

    def clean(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in self._TRUE:
                return True
            if lowered in self._FALSE:
                return False
        raise InvalidValue("Expected a boolean (true or false).")


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

    def clean(self, value: Any) -> str:
        if value not in self.choices:
            allowed = ", ".join(repr(c) for c in self.choices)
            raise InvalidValue(f"Must be one of {allowed}.")
        return value

    def _extra_schema(self) -> dict[str, Any]:
        return {"choices": list(self.choices)}


class Url(String):
    """An absolute URL whose scheme is restricted (http/https by default).

    This only checks the URL's shape. Fetching a user-supplied URL must go through
    ``widget_hub.security.safe_fetch`` to be protected against SSRF.
    """

    type_name = "url"

    def __init__(
        self, name: str, *, schemes: Sequence[str] = ("http", "https"), **kwargs: Any
    ) -> None:
        self.schemes = tuple(s.lower() for s in schemes)
        kwargs.setdefault("max_length", 2048)
        super().__init__(name, **kwargs)

    def _check_declaration(self) -> None:
        super()._check_declaration()
        if not self.schemes:
            raise ImproperlyConfigured(f"{self!r}: schemes must not be empty.")

    def clean(self, value: Any) -> str:
        value = super().clean(value)
        if any(c.isspace() for c in value):
            raise InvalidValue("A URL must not contain whitespace.")
        try:
            parts = urlsplit(value)
            parts.port  # noqa: B018 - raises ValueError on an invalid port
        except ValueError:
            raise InvalidValue("Enter a valid URL.") from None
        if parts.scheme.lower() not in self.schemes:
            raise InvalidValue(f"URL scheme must be one of: {', '.join(self.schemes)}.")
        if not parts.hostname:
            raise InvalidValue("URL must include a host name.")
        if parts.username or parts.password:
            raise InvalidValue("URL must not contain credentials.")
        return value

    def _extra_schema(self) -> dict[str, Any]:
        return {**super()._extra_schema(), "schemes": list(self.schemes)}


def _bounds(**bounds: int | None) -> dict[str, int]:
    return {k: v for k, v in bounds.items() if v is not None}


def validate_params(declared: Sequence[Param], data: Any) -> dict[str, Any]:
    """Validate ``data`` against ``declared`` parameters.

    Returns a new dict containing every declared parameter: submitted values are normalised,
    omitted ones get their default (or ``None`` when optional without default). Unknown keys
    are rejected. All problems are reported together in a :class:`ParamValidationError`.
    """
    if data is None:
        data = {}
    if not isinstance(data, Mapping):
        raise ParamValidationError({"__all__": "Parameters must be a JSON object."})
    errors: dict[str, str] = {}
    known = {p.name for p in declared}
    for key in data:
        if key not in known:
            errors[str(key)] = "Unknown parameter."
    cleaned: dict[str, Any] = {}
    for param in declared:
        value = data.get(param.name, MISSING)
        if value is MISSING or value is None or (isinstance(value, str) and not value.strip()):
            if param.has_default:
                cleaned[param.name] = param.default
            elif param.required:
                errors[param.name] = "This parameter is required."
            else:
                cleaned[param.name] = None
            continue
        try:
            cleaned[param.name] = param.clean(value)
        except InvalidValue as exc:
            errors[param.name] = str(exc)
    if errors:
        raise ParamValidationError(errors)
    return cleaned
