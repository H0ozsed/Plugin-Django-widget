"""Declaration API: :class:`Service` and :class:`Widget`.

Example::

    from widget_hub import Service, Widget, params, register

    weather = Service("weather", description="Open-Meteo forecasts")

    @register
    class CityTemperature(Widget):
        service = weather
        name = "city_temperature"
        description = "Current temperature for a city"
        params = [params.String("city", max_length=100)]

        def fetch(self, params, context):
            ...
"""

from __future__ import annotations

from typing import Any, ClassVar

from django.core.exceptions import ImproperlyConfigured

from .params import Param, check_name


class Service:
    """A group of widgets backed by the same external source.

    :param name: unique identifier, exposed in ``/about.json``.
    :param description: optional human-readable description.
    """

    def __init__(self, name: str, *, description: str = "") -> None:
        self.name = check_name("service", name)
        self.description = description

    def __repr__(self) -> str:
        return f"Service({self.name!r})"


class Widget:
    """Base class for a widget. Subclass it, set the class attributes and implement :meth:`fetch`.

    Class attributes:

    * ``service`` (:class:`Service`, required)
    * ``name`` (``str``, required, unique within the service)
    * ``description`` (``str``)
    * ``params`` (list of :class:`~widget_hub.params.Param`)
    * ``default_refresh_rate`` (seconds, ``int``)
    """

    service: ClassVar[Service]
    name: ClassVar[str]
    description: ClassVar[str] = ""
    params: ClassVar[list[Param]] = []
    default_refresh_rate: ClassVar[int] = 300

    @classmethod
    def check_declaration(cls) -> None:
        """Validate the class attributes, raising ImproperlyConfigured with a precise message."""
        label = f"{cls.__module__}.{cls.__qualname__}"
        service = getattr(cls, "service", None)
        if not isinstance(service, Service):
            raise ImproperlyConfigured(f"{label}.service must be a widget_hub.Service instance.")
        check_name(f"widget ({label})", getattr(cls, "name", None))
        seen: set[str] = set()
        for param in cls.params:
            if not isinstance(param, Param):
                raise ImproperlyConfigured(
                    f"{label}.params must only contain widget_hub.params.Param instances, "
                    f"got {param!r}."
                )
            if param.name in seen:
                raise ImproperlyConfigured(f"{label}: parameter {param.name!r} declared twice.")
            seen.add(param.name)
        if not isinstance(cls.default_refresh_rate, int) or cls.default_refresh_rate <= 0:
            raise ImproperlyConfigured(f"{label}.default_refresh_rate must be a positive integer.")

    def fetch(self, params: dict[str, Any], context: Any) -> Any:
        """Return JSON-serialisable data for one widget instance.

        :param params: validated parameter values (defaults applied).
        :param context: request-independent information about the call (owner, credentials...).
        """
        raise NotImplementedError(f"{type(self).__qualname__} must implement fetch().")
