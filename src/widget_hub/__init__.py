"""django-widget-hub: declare dashboard widgets once, get the rest for free."""

from . import params
from .exceptions import ParamValidationError, WidgetError
from .registry import register, registry
from .widgets import Service, Widget

__version__ = "0.1.0"

__all__ = [
    "ParamValidationError",
    "Service",
    "Widget",
    "WidgetError",
    "params",
    "register",
    "registry",
]
