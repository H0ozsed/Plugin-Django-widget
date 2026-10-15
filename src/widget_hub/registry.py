"""The widget registry: single source of truth for services and widgets.

Widgets are registered with :func:`register` (usually as a class decorator) from a
``widgets.py`` module in any installed app; those modules are imported automatically at
startup. Registering two services or two widgets under the same name raises
:class:`~django.core.exceptions.ImproperlyConfigured` immediately, so the server refuses
to start instead of silently hiding a widget.
"""

from __future__ import annotations

from collections.abc import Iterator

from django.core.exceptions import ImproperlyConfigured

from .widgets import Service, Widget


def _origin(obj: object) -> str:
    cls = obj if isinstance(obj, type) else type(obj)
    return f"{cls.__module__}.{cls.__qualname__}"


class WidgetRegistry:
    """Holds registered widgets, keyed by ``(service name, widget name)``."""

    def __init__(self) -> None:
        self._services: dict[str, Service] = {}
        self._widgets: dict[tuple[str, str], Widget] = {}

    def register(self, widget_class: type[Widget]) -> type[Widget]:
        """Validate and register ``widget_class``; returns it so it can be used as a decorator."""
        if not (isinstance(widget_class, type) and issubclass(widget_class, Widget)):
            raise ImproperlyConfigured(
                f"register() expects a Widget subclass, got {widget_class!r}."
            )
        widget_class.check_declaration()
        service = widget_class.service
        known = self._services.get(service.name)
        if known is not None and known is not service:
            raise ImproperlyConfigured(
                f"Duplicate service name {service.name!r}: two different Service objects use it "
                f"(second one used by {_origin(widget_class)}). Reuse the same Service instance "
                "or rename one."
            )
        key = (service.name, widget_class.name)
        if key in self._widgets:
            raise ImproperlyConfigured(
                f"Duplicate widget {service.name}.{widget_class.name}: already registered by "
                f"{_origin(self._widgets[key])}, registered again by {_origin(widget_class)}."
            )
        self._services[service.name] = service
        self._widgets[key] = widget_class()
        return widget_class

    def get(self, service_name: str, widget_name: str) -> Widget | None:
        """Return the registered widget instance, or ``None`` if unknown."""
        return self._widgets.get((service_name, widget_name))

    def services(self) -> list[Service]:
        """Return registered services in registration order."""
        return list(self._services.values())

    def widgets_of(self, service_name: str) -> list[Widget]:
        """Return the widgets of one service in registration order."""
        return [w for (s, _), w in self._widgets.items() if s == service_name]

    def __iter__(self) -> Iterator[Widget]:
        return iter(list(self._widgets.values()))

    def __len__(self) -> int:
        return len(self._widgets)

    def clear(self) -> None:
        """Forget every registration (meant for tests)."""
        self._services.clear()
        self._widgets.clear()


registry = WidgetRegistry()
"""The default, process-wide registry."""


def register(widget_class: type[Widget]) -> type[Widget]:
    """Register ``widget_class`` in the default :data:`registry` (class decorator)."""
    return registry.register(widget_class)
