"""Tests of the demo widgets with canned HTTP responses (no network).

Run with: pytest example/demo_widgets --ds=example_project.settings
"""

import json

import pytest

from demo_widgets import widgets
from widget_hub import WidgetError, registry
from widget_hub.security import SafeResponse
from widget_hub.services import FetchContext


def response(body, status=200):
    content = body if isinstance(body, bytes) else json.dumps(body).encode()
    return SafeResponse(status, {"content-type": "application/json"}, content, "https://x.test/")


def ctx(credential=None):
    return FetchContext(owner=None, instance_id=1, credential=credential)


def test_the_three_widgets_are_registered():
    assert registry.get("weather", "current")
    assert registry.get("rss", "latest")
    assert registry.get("github", "my_repositories").uses_credential


class TestWeather:
    def test_fetch(self, monkeypatch):
        calls = []

        def fake(url, **kwargs):
            calls.append((url, kwargs["params"]))
            if "geocoding" in url:
                return response(
                    {
                        "results": [
                            {
                                "name": "Paris",
                                "country": "France",
                                "latitude": 48.85,
                                "longitude": 2.35,
                            }
                        ]
                    }
                )
            return response(
                {
                    "current": {
                        "temperature_2m": 12.5,
                        "apparent_temperature": 11,
                        "relative_humidity_2m": 80,
                        "wind_speed_10m": 9.4,
                    }
                }
            )

        monkeypatch.setattr(widgets, "safe_fetch", fake)
        data = widgets.CurrentWeather().fetch({"city": "Paris", "unit": "celsius"}, ctx())
        assert data == {
            "city": "Paris, France",
            "temperature": "12.5 °C",
            "feels_like": "11 °C",
            "humidity": "80 %",
            "wind": "9.4 km/h",
        }
        assert calls[1][1]["temperature_unit"] == "celsius"

    def test_unknown_city(self, monkeypatch):
        monkeypatch.setattr(widgets, "safe_fetch", lambda url, **kw: response({"results": []}))
        with pytest.raises(WidgetError, match="No city called 'Atlantis'") as info:
            widgets.CurrentWeather().fetch({"city": "Atlantis", "unit": "celsius"}, ctx())
        assert info.value.status == 404


RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>Blog</title>
<item><title>One</title><link>https://b.test/1</link><pubDate>Mon, 01 Jan 2026</pubDate></item>
<item><title>Two</title><link>https://b.test/2</link></item>
<item><title>Three</title><link>https://b.test/3</link></item></channel></rss>"""

ATOM = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>News</title>
<entry><title>A</title><link href="https://n.test/a"/><updated>2026-01-01T00:00:00Z</updated></entry>
</feed>"""


class TestRss:
    def test_rss(self, monkeypatch):
        seen = {}

        def fake(url, **kwargs):
            seen["url"] = url
            return response(RSS)

        monkeypatch.setattr(widgets, "safe_fetch", fake)
        data = widgets.LatestArticles().fetch({"feed": "https://b.test/feed", "count": 2}, ctx())
        assert seen["url"] == "https://b.test/feed"
        assert data == {
            "title": "Blog",
            "items": [
                {"title": "One", "link": "https://b.test/1", "published": "Mon, 01 Jan 2026"},
                {"title": "Two", "link": "https://b.test/2", "published": None},
            ],
        }

    def test_atom(self):
        assert widgets.parse_feed(ATOM, 5) == {
            "title": "News",
            "items": [
                {"title": "A", "link": "https://n.test/a", "published": "2026-01-01T00:00:00Z"}
            ],
        }

    @pytest.mark.parametrize(
        "body",
        [b"<html><body>nope</body></html>", b"not xml at all", b"<rss><nochannel/></rss>"],
    )
    def test_not_a_feed(self, body):
        with pytest.raises(WidgetError, match="not an RSS or Atom feed"):
            widgets.parse_feed(body, 5)

    def test_dtd_is_refused(self):
        bomb = b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaa">]><rss>&a;</rss>'
        with pytest.raises(WidgetError, match="DOCTYPE"):
            widgets.parse_feed(bomb, 5)

    def test_http_error(self, monkeypatch):
        monkeypatch.setattr(widgets, "safe_fetch", lambda url, **kw: response(b"", status=404))
        with pytest.raises(WidgetError, match="HTTP 404"):
            widgets.LatestArticles().fetch({"feed": "https://b.test/x", "count": 5}, ctx())


class TestGithub:
    def test_requires_a_token(self):
        with pytest.raises(WidgetError, match="Add a GitHub personal access token"):
            widgets.MyRepositories().fetch({"count": 5}, ctx())

    def test_uses_the_token(self, monkeypatch):
        seen = {}

        def fake(url, **kwargs):
            seen.update(kwargs)
            return response(
                [
                    {
                        "full_name": "me/app",
                        "html_url": "https://github.com/me/app",
                        "stargazers_count": 3,
                        "updated_at": "2026-10-01T00:00:00Z",
                    }
                ]
            )

        monkeypatch.setattr(widgets, "safe_fetch", fake)
        data = widgets.MyRepositories().fetch({"count": 1}, ctx("ghp_token"))
        assert seen["headers"]["Authorization"] == "Bearer ghp_token"
        assert seen["params"] == {"sort": "updated", "per_page": 1}
        assert data["repositories"][0]["name"] == "me/app"

    @pytest.mark.parametrize(
        ("status", "message"), [(401, "refused the token"), (500, "not answering")]
    )
    def test_errors(self, monkeypatch, status, message):
        monkeypatch.setattr(widgets, "safe_fetch", lambda url, **kw: response({}, status=status))
        with pytest.raises(WidgetError, match=message):
            widgets.MyRepositories().fetch({"count": 1}, ctx("t"))
