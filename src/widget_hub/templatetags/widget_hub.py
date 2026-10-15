"""Template tags of widget_hub: ``{% load widget_hub %}{% dashboard %}``."""

from __future__ import annotations

from typing import Any

from django import template
from django.conf import settings
from django.urls import reverse

from .. import conf

register = template.Library()


def _csrf_header_name() -> str:
    """Turn ``settings.CSRF_HEADER_NAME`` (a META key) into an HTTP header name."""
    name = settings.CSRF_HEADER_NAME
    return name.removeprefix("HTTP_").replace("_", "-")


@register.inclusion_tag("widget_hub/dashboard.html", takes_context=True)
def dashboard(context: template.Context, title: str = "Dashboard") -> dict[str, Any]:
    """Render the current user's dashboard (grid, settings forms, auto-refresh).

    Requires ``include("widget_hub.urls")`` and a request in the context. Anonymous users see a
    short message instead. Only URLs and limits are written in the page; no secret is inlined.
    """
    request = context.get("request")
    user = getattr(request, "user", None)
    return {
        "title": title,
        "authenticated": bool(user and user.is_authenticated),
        "csrf_token": context.get("csrf_token"),
        "csrf_header": _csrf_header_name(),
        "urls": {
            "catalog": reverse("widget_hub:catalog"),
            "instances": reverse("widget_hub:instances"),
            "credentials": reverse("widget_hub:credentials"),
        },
        "min_refresh": conf.get("MIN_REFRESH_RATE"),
        "max_refresh": conf.get("MAX_REFRESH_RATE"),
    }
