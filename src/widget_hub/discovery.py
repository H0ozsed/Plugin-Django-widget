"""The ``/about.json`` discovery document, in the Epitech Dashboard format::

{
  "client": {"host": "10.101.53.35"},
  "server": {
    "current_time": 1531680780,
    "services": [
      {"name": "weather",
       "widgets": [{"name": "city_temperature",
                    "description": "Display temperature for a city",
                    "params": [{"name": "city", "type": "string"}]}]}
    ]
  }
}
"""

from __future__ import annotations

import time
from typing import Any

from django.http import HttpRequest

from . import conf
from .registry import WidgetRegistry, registry


def client_host(request: HttpRequest) -> str | None:
    """Return the client IP: ``REMOTE_ADDR``, or the first ``X-Forwarded-For`` entry when the
    ``ABOUT_TRUST_X_FORWARDED_FOR`` setting says a trusted reverse proxy sets that header."""
    if conf.get("ABOUT_TRUST_X_FORWARDED_FOR"):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.META.get("REMOTE_ADDR")


def services_document(source: WidgetRegistry = registry) -> list[dict[str, Any]]:
    """Return the ``services`` list: every registered service with its widgets and params."""
    return [
        {
            "name": service.name,
            "widgets": [
                {
                    "name": widget.name,
                    "description": widget.description,
                    "params": [{"name": p.name, "type": p.about_type} for p in widget.params],
                }
                for widget in source.widgets_of(service.name)
            ],
        }
        for service in source.services()
    ]


def about_document(request: HttpRequest, source: WidgetRegistry = registry) -> dict[str, Any]:
    """Return the full ``/about.json`` document for ``request``."""
    return {
        "client": {"host": client_host(request)},
        "server": {"current_time": int(time.time()), "services": services_document(source)},
    }
