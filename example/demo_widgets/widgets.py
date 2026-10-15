"""Three example widgets, one per typical situation:

* ``weather.current``: a public API with fixed URLs (Open-Meteo, no key).
* ``rss.latest``: a URL typed by the user, fetched with ``safe_fetch`` (SSRF-protected).
* ``github.my_repositories``: needs the user's personal token, stored encrypted.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from widget_hub import Service, Widget, WidgetError, params, register
from widget_hub.security import safe_fetch

weather = Service("weather", description="Open-Meteo forecasts (no API key)")
rss = Service("rss", description="Any RSS or Atom feed")
github = Service("github", description="GitHub, with your personal access token")


@register
class CurrentWeather(Widget):
    """Current conditions for a city."""

    service = weather
    name = "current"
    description = "Current weather in a city"
    default_refresh_rate = 600
    params = [
        params.String("city", min_length=1, max_length=100),
        params.Choice("unit", choices=["celsius", "fahrenheit"], default="celsius"),
    ]

    def fetch(self, params, context):
        places = safe_fetch(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": params["city"], "count": 1},
        ).json()
        if not places.get("results"):
            raise WidgetError(f"No city called {params['city']!r} was found.", 404)
        place = places["results"][0]
        forecast = safe_fetch(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "current": "temperature_2m,apparent_temperature,relative_humidity_2m,"
                "wind_speed_10m",
                "temperature_unit": params["unit"],
            },
        )
        if forecast.status != 200:
            raise WidgetError("Open-Meteo is not answering right now.", 502)
        current = forecast.json()["current"]
        symbol = "°C" if params["unit"] == "celsius" else "°F"
        return {
            "city": f"{place['name']}, {place.get('country', '')}".rstrip(", "),
            "temperature": f"{current['temperature_2m']} {symbol}",
            "feels_like": f"{current['apparent_temperature']} {symbol}",
            "humidity": f"{current['relative_humidity_2m']} %",
            "wind": f"{current['wind_speed_10m']} km/h",
        }


ATOM = "{http://www.w3.org/2005/Atom}"


def parse_feed(content: bytes, limit: int) -> dict:
    """Parse an RSS 2.0 or Atom document into ``{"title": ..., "items": [...]}``.

    Documents with a DTD are refused: feeds do not need one, and it rules out entity-expansion
    attacks whatever the expat version.
    """
    if re.search(rb"<!DOCTYPE", content, re.IGNORECASE):
        raise WidgetError("Feeds with a DOCTYPE are not supported.", 422)
    try:
        root = ET.fromstring(content)  # noqa: S314 - DTDs refused above
    except ET.ParseError:
        raise WidgetError("This URL is not an RSS or Atom feed.", 422) from None
    if root.tag == f"{ATOM}feed":
        items = []
        for entry in root.findall(f"{ATOM}entry")[:limit]:
            link = entry.find(f"{ATOM}link")
            items.append(
                {
                    "title": entry.findtext(f"{ATOM}title", "").strip(),
                    "link": link.get("href") if link is not None else None,
                    "published": entry.findtext(f"{ATOM}updated"),
                }
            )
        return {"title": root.findtext(f"{ATOM}title", "").strip(), "items": items}
    channel = root.find("channel")
    if root.tag != "rss" or channel is None:
        raise WidgetError("This URL is not an RSS or Atom feed.", 422)
    return {
        "title": channel.findtext("title", "").strip(),
        "items": [
            {
                "title": item.findtext("title", "").strip(),
                "link": item.findtext("link"),
                "published": item.findtext("pubDate"),
            }
            for item in channel.findall("item")[:limit]
        ],
    }


@register
class LatestArticles(Widget):
    """Latest entries of a feed whose URL the user types: fetched through ``safe_fetch``."""

    service = rss
    name = "latest"
    description = "Latest articles of a feed"
    default_refresh_rate = 900
    params = [
        params.Url("feed", help_text="Address of an RSS or Atom feed"),
        params.Integer("count", min_value=1, max_value=20, default=5),
    ]

    def fetch(self, params, context):
        response = safe_fetch(params["feed"], max_bytes=1_000_000)
        if response.status != 200:
            raise WidgetError(f"The feed answered with HTTP {response.status}.", 502)
        return parse_feed(response.content, params["count"])


@register
class MyRepositories(Widget):
    """The user's most recently updated repositories, read with their own token."""

    service = github
    name = "my_repositories"
    description = "My latest GitHub repositories"
    default_refresh_rate = 900
    cache_per_owner = True
    uses_credential = True
    params = [params.Integer("count", min_value=1, max_value=10, default=5)]

    def fetch(self, params, context):
        if not context.credential:
            raise WidgetError("Add a GitHub personal access token in this widget's settings.", 400)
        response = safe_fetch(
            "https://api.github.com/user/repos",
            params={"sort": "updated", "per_page": params["count"]},
            headers={
                "Authorization": f"Bearer {context.credential}",
                "Accept": "application/vnd.github+json",
            },
        )
        if response.status in (401, 403):
            raise WidgetError("GitHub refused the token; update it in the widget settings.", 400)
        if response.status != 200:
            raise WidgetError("GitHub is not answering right now.", 502)
        return {
            "repositories": [
                {
                    "name": repo["full_name"],
                    "url": repo["html_url"],
                    "stars": repo["stargazers_count"],
                    "updated": repo["updated_at"],
                }
                for repo in response.json()
            ]
        }
