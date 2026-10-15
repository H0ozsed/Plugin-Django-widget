"""A few behaviours of the migrated widgets, with canned HTTP responses."""

import json

import pytest
from services import widgets

from widget_hub import WidgetError
from widget_hub.security import SafeResponse
from widget_hub.services import FetchContext


def response(body, status=200):
    content = body if isinstance(body, bytes) else json.dumps(body).encode()
    return SafeResponse(status, {}, content, "https://x.test/")


def ctx(credential=None):
    return FetchContext(owner=None, instance_id=1, credential=credential)


def test_clock_now_has_a_backend():
    data = widgets.Clock().fetch({"timezone": "Indian/Reunion"}, ctx())
    assert data["timezone"] == "Indian/Reunion" and data["iso"].endswith("+04:00")
    with pytest.raises(WidgetError, match="Fuseau horaire inconnu"):
        widgets.Clock().fetch({"timezone": "Mars/Olympus"}, ctx())


def test_recent_commits_sends_the_stored_token_only_when_present(monkeypatch):
    seen = []
    monkeypatch.setattr(
        widgets, "safe_fetch", lambda url, **kw: seen.append(kw["headers"]) or response([])
    )
    widgets.RecentCommits().fetch({"owner": "o", "repo": "r"}, ctx())
    widgets.RecentCommits().fetch({"owner": "o", "repo": "r"}, ctx("ghp_x"))
    assert "Authorization" not in seen[0]
    assert seen[1]["Authorization"] == "Bearer ghp_x"


def test_rss_goes_through_safe_fetch(monkeypatch):
    feed = (
        b"<rss version='2.0'><channel><title>T</title>"
        b"<item><title>A</title><link>https://t.test/a</link></item></channel></rss>"
    )
    urls = []
    monkeypatch.setattr(widgets, "safe_fetch", lambda url, **kw: urls.append(url) or response(feed))
    data = widgets.ArticleList().fetch({"link": "https://t.test/rss", "number": 5}, ctx())
    assert urls == ["https://t.test/rss"]
    assert data == {
        "title": "T",
        "articles": [{"title": "A", "link": "https://t.test/a", "published": None}],
    }


def test_unknown_city(monkeypatch):
    monkeypatch.setattr(widgets, "safe_fetch", lambda url, **kw: response({}))
    with pytest.raises(WidgetError, match="Ville introuvable") as info:
        widgets.CityTemperature().fetch({"city": "Atlantis"}, ctx())
    assert info.value.status == 404
