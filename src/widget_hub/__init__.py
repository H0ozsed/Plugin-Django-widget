"""django-widget-hub: declare dashboard widgets once, get the rest for free."""

from . import params
from .registry import register, registry
from .widgets import Service, Widget

__version__ = "0.1.0.dev0"

__all__ = ["Service", "Widget", "params", "register", "registry"]
