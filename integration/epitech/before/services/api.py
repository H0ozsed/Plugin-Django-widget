"""
django-ninja API for the dashboard backend.

Every route below is protected by `x_session_token_auth` (a valid
"X-Session-Token" header) or `django_auth` (Django session cookie, used by
the browser frontend), except `/about.json`, `/geocode` and `/nasa_picture`,
which are deliberately public. `/about.json` is the entry point used by the
automated grading script.

Each view function's docstring below is not just documentation for humans:
django-ninja reads it automatically and uses it as the route's "description"
in the generated OpenAPI schema, visible at /docs and /openapi.json.
"""

import ipaddress
import socket
import time
from typing import Optional
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from django.contrib.auth import logout
from django.shortcuts import get_object_or_404

from allauth.headless.contrib.ninja.security import x_session_token_auth
from ninja import NinjaAPI, Schema
from ninja.security import django_auth
from services.registry import SERVICES
from services.models import (
    Profile,
    ServiceCredential,
    WidgetInstance,
    decrypt_token,
    encrypt_token,
)


api = NinjaAPI(auth=[x_session_token_auth, django_auth])
"""The API instance every route below is registered on. `auth=` is set
globally (fail-closed): a new route is protected by default unless it
explicitly opts out with `auth=None`, as `about` does below. Two methods are
accepted: the session token (grading script) or the session cookie (browser
frontend). In both cases `request.auth` is the authenticated user."""


@api.get("/about.json", auth=None)
def about(request):
    """Public entry point describing the server and its available services.

    Returns the client's host, the server's current time, and the full list
    of services/widgets from `services.registry.SERVICES`, in the exact shape
    the project spec requires. Used by the automated grading script — must
    stay reachable without authentication.

    `client.host` prefers `X-Forwarded-For` (set by a real reverse proxy) and
    falls back to `REMOTE_ADDR`. Without a reverse proxy in front of this
    service, `REMOTE_ADDR` reflects the Docker bridge network's gateway, not
    the true external client — a known limitation of plain Docker port
    publishing (no HTTP-level proxy involved), not a bug in this code. See
    docs/project/mid-term.md.
    """
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    client_host = forwarded_for.split(",")[0].strip() if forwarded_for else request.META.get("REMOTE_ADDR")
    return {
        "client": {
            "host": client_host,
        },
        "server": {
            "current_time": int(time.time()),
            "services": SERVICES,
        },
    }


@api.get("/geocode", auth=None)
def geocode(request, name: str):
    """Search cities by name, via the Open-Meteo geocoding API."""
    try:
        response = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": name, "count": 5, "language": "fr"},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])
        return {
            "results": [
                {
                    "name": r["name"],
                    "country": r.get("country"),
                    "admin1": r.get("admin1"),
                    "latitude": r["latitude"],
                    "longitude": r["longitude"],
                }
                for r in results
            ]
        }
    except requests.RequestException as error:
        return api.create_response(
            request,
            {"error": "Impossible de rechercher cette ville", "details": str(error)},
            status=503,
        )


@api.get("/weather")
def weather(request, latitude: float, longitude: float):
    """Current weather for a given location, via the Open-Meteo API.

    Backs the "weather" service's `city_temperature` widget. No API key is
    required by Open-Meteo. Returns 503 if the upstream API cannot be reached.
    """
    try:
        response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": (
                    "temperature_2m,"
                    "apparent_temperature,"
                    "relative_humidity_2m,"
                    "wind_speed_10m,"
                    "weather_code"
                ),
                "timezone": "auto",
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        return {
            "latitude": data["latitude"],
            "longitude": data["longitude"],
            "temperature": data["current"]["temperature_2m"],
            "feels_like": data["current"]["apparent_temperature"],
            "humidity": data["current"]["relative_humidity_2m"],
            "wind_speed": data["current"]["wind_speed_10m"],
            "weather_code": data["current"]["weather_code"],
        }

    except requests.RequestException as error:
        return api.create_response(
            request,
            {
                "error": "Impossible de récupérer la météo",
                "details": str(error),
            },
            status=503,
        )


@api.get("/forecast")
def forecast(request, latitude: float, longitude: float, days: int = 5):
    """Daily forecast (min/max temperature, sky) for the next `days` days,
    via the Open-Meteo API.

    Backs the "weather" service's `city_forecast` widget. `days` must be
    between 1 and 16 (Open-Meteo's limit), otherwise 400 is returned.
    Returns 503 if the upstream API cannot be reached.
    """
    if not 1 <= days <= 16:
        return api.create_response(
            request, {"error": "days must be between 1 and 16"}, status=400
        )
    try:
        response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "daily": "temperature_2m_max,temperature_2m_min,weather_code",
                "forecast_days": days,
                "timezone": "auto",
            },
            timeout=10,
        )
        response.raise_for_status()
        daily = response.json()["daily"]
        return {
            "days": [
                {
                    "date": date,
                    "temperature_max": t_max,
                    "temperature_min": t_min,
                    "weather_code": code,
                }
                for date, t_max, t_min, code in zip(
                    daily["time"],
                    daily["temperature_2m_max"],
                    daily["temperature_2m_min"],
                    daily["weather_code"],
                )
            ],
        }

    except requests.RequestException as error:
        return api.create_response(
            request,
            {
                "error": "Impossible de récupérer les prévisions",
                "details": str(error),
            },
            status=503,
        )


@api.get("/steam")
def steam(request, game_id: int):
    """Global achievement completion rates for a Steam game.

    Backs the "steam" service's `global_achievements` widget. This is a
    global statistic (across all Steam players), not a per-user achievement
    list, so no Steam account or API key is needed. Returns 503 if the
    upstream API cannot be reached.
    """
    try:
        response = requests.get(
            "https://api.steampowered.com/ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2/",
            params={
                "gameid": game_id,
                "format": "json",
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        achievement_data = data.get("achievementpercentages", {})
        achievements = achievement_data.get("achievements", [])
        return {
            "game_id": game_id,
            "achievements": achievements,
        }

    except requests.RequestException as error:
        return api.create_response(
            request,
            {
                "error": "Impossible de récupérer les données Steam",
                "details": str(error),
            },
            status=503,
        )


@api.get("/nasa_picture", auth=None)
def nasa_picture(request, days_ago: int = 0):
    """NASA's Astronomy Picture of the Day, from `days_ago` days ago
    (0 = today).

    Backs the "nasa_picture" service's `daily_picture` widget. This endpoint
    (science.nasa.gov) ignores date filters, but returns one picture per
    page, newest first: page N is the picture from N - 1 days ago. (The
    official api.nasa.gov endpoint does accept a date, but now returns a
    placeholder NASA logo instead of the real image.) Returns 400 if
    `days_ago` is negative, 503 if the upstream API cannot be reached.
    """
    if days_ago < 0:
        return api.create_response(
            request, {"error": "days_ago must be 0 or more"}, status=400
        )
    try:
        response = requests.get(
            "https://science.nasa.gov/wp-json/wp/v2/apod-basic",
            params={"per_page": 1, "page": days_ago + 1},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()[0]
        return {
            "date": data.get("date"),
            "title": data.get("title"),
            "description": data.get("explanation"),
            "image_url": data.get("hdurl"),
            "article_url": data.get("url"),
            "media_type": data.get("media_type"),
            "alt": data.get("alt"),
            "credit": data.get("credit"),
            "copyright": data.get("copyright"),
        }
    except requests.RequestException as error:
        return api.create_response(
            request,
            {
                "error": "Impossible de récupérer l'image du jour de la NASA",
                "details": str(error),
            },
            status=503,
        )


def _is_public_url(url):
    """True if `url` is http(s) and its host only resolves to public IPs.

    The RSS widget makes the server download an address chosen by the user.
    Without this check, a user could make it reach services that are only
    reachable from inside (the database, Mailpit, the Docker network,
    127.0.0.1...) — an attack known as SSRF.
    """
    parts = urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return False
    try:
        addresses = socket.getaddrinfo(parts.hostname, parts.port or 443)
    except socket.gaierror:
        return False
    return all(ipaddress.ip_address(info[4][0]).is_global for info in addresses)


@api.get("/rss")
def rss(request, link: str, number: int = 5):
    """Latest `number` articles of an RSS or Atom feed.

    Backs the "rss" service's `article_list` widget. The feed is downloaded
    with `requests` (to keep a timeout) and parsed with `feedparser`.
    `number` must be between 1 and 20, and `link` a public http(s) URL (see
    `_is_public_url`), otherwise 400 is returned. Returns 503 if the feed
    cannot be reached or read.
    """
    if not 1 <= number <= 20:
        return api.create_response(
            request, {"error": "number must be between 1 and 20"}, status=400
        )
    try:
        # Follow redirects by hand, so that every address visited is checked.
        url = link
        for _ in range(4):
            if not _is_public_url(url):
                return api.create_response(
                    request,
                    {"error": "link must be a public http(s) URL"},
                    status=400,
                )
            response = requests.get(url, timeout=10, allow_redirects=False)
            if not response.is_redirect:
                break
            url = urljoin(url, response.headers["Location"])
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        if feed.bozo and not feed.entries:
            raise ValueError("not a valid RSS/Atom feed")
        return {
            "title": feed.feed.get("title", link),
            "articles": [
                {
                    "title": entry.get("title"),
                    "link": entry.get("link"),
                    "published": entry.get("published"),
                }
                for entry in feed.entries[:number]
            ],
        }

    except (requests.RequestException, ValueError) as error:
        return api.create_response(
            request,
            {
                "error": "Impossible de lire le flux RSS",
                "details": str(error),
            },
            status=503,
        )


@api.get("/github")
def github(request, username: str):
    """Public GitHub profile and 5 most recently updated repositories.

    Backs the "github" service's `user_profile` widget. Uses GitHub's public
    API (no token, 60 requests per hour). Returns 503 if the user doesn't
    exist or GitHub cannot be reached.
    """
    try:
        headers = {
            "Accept": "application/vnd.github+json",
        }

        user_response = requests.get(
            f"https://api.github.com/users/{username}",
            headers=headers,
            timeout=10,
        )
        user_response.raise_for_status()

        repos_response = requests.get(
            f"https://api.github.com/users/{username}/repos",
            headers=headers,
            params={
                "sort": "updated",
                "per_page": 5,
            },
            timeout=10,
        )
        repos_response.raise_for_status()

        user = user_response.json()
        repos = repos_response.json()

        return {
            "user": {
                "login": user.get("login"),
                "name": user.get("name"),
                "avatar_url": user.get("avatar_url"),
                "html_url": user.get("html_url"),
                "public_repos": user.get("public_repos"),
                "followers": user.get("followers"),
                "following": user.get("following"),
            },
            "repos": [
                {
                    "name": repo.get("name"),
                    "html_url": repo.get("html_url"),
                    "description": repo.get("description"),
                    "language": repo.get("language"),
                    "stargazers_count": repo.get("stargazers_count"),
                }
                for repo in repos
            ],
        }

    except requests.RequestException as error:
        return api.create_response(
            request,
            {
                "error": "Impossible de récupérer les données GitHub",
                "details": str(error),
            },
            status=503,
        )

class Item_sub(Schema):
    """Expected JSON body for `POST /services/github/subscribe`: a single
    personal GitHub token, provided by the user."""

    token: str
    """The user's personal GitHub token, stored encrypted in
    `ServiceCredential` and later sent to the GitHub API as
    `Authorization: Bearer <token>`."""


@api.post("/services/github/subscribe")
def github_subscribe(request, item: Item_sub):
    """Link a personal GitHub token to the authenticated user.

    Optional for `github_activity` (which falls back to GitHub's public
    API), but raises its rate limit and gives access to private
    repositories. The token is encrypted before being stored. Uses
    `update_or_create` so re-subscribing replaces the previous token instead
    of creating a duplicate row.
    """
    ServiceCredential.objects.update_or_create(
        user=request.auth,
        service_name="github",
        defaults={"token": encrypt_token(item.token)},
    )
    return {"message": "GitHub service subscribed successfully."}



@api.get("/github_activity")
def github_activity(request, owner: str, repo: str):
    """Last 10 commits of a GitHub repository.

    Backs the "github" service's `recent_commits` widget. Public repositories
    need no token (GitHub then allows 60 requests per hour); if the user has
    stored a personal token with `github_subscribe`, it is sent too, which
    raises that limit and gives access to their private repositories.
    Returns 503 if GitHub rejects the request or cannot be reached (unknown
    repository, rate limit, invalid token).
    """
    headers = {"Accept": "application/vnd.github+json"}
    service_credential = ServiceCredential.objects.filter(
        user=request.auth, service_name="github"
    ).first()
    if service_credential is not None:
        headers["Authorization"] = f"Bearer {decrypt_token(service_credential.token)}"
    try:
        response = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/commits",
            headers=headers,
            params={"per_page": 10},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        commits = []
        for commit in data:
            commits.append({
                "sha": commit["sha"],
                "author": commit["commit"]["author"]["name"],
                "message": commit["commit"]["message"],
                "date": commit["commit"]["author"]["date"],
            })
        return {
            "owner": owner,
            "repo": repo,
            "commits": commits,
        }

    except requests.RequestException as error:
        return api.create_response(
            request,
            {
                "error": "Impossible de récupérer les activités GitHub",
                "details": str(error),
            },
            status=503,
        )


class WidgetInstanceIn(Schema):
    """Expected JSON body for `POST /dashboard/widgets`: a new widget to add
    to the authenticated user's dashboard."""

    service_name: str
    """Which service this widget belongs to, e.g. `"weather"` — must match a
    `name` in `services.registry.SERVICES`."""

    widget_name: str
    """Which widget of that service, e.g. `"city_temperature"`."""

    params: dict = {}
    """The values configured for this instance, e.g. `{"city": "Paris"}`."""

    refresh_rate: int = 60
    """How often, in seconds, the frontend should re-fetch this widget."""

    position: dict = {}
    """Where this widget sits on the dashboard grid, e.g.
    `{"x": 0, "y": 0, "w": 2, "h": 2}`."""


class WidgetInstancePatch(Schema):
    """Expected JSON body for `PATCH /dashboard/widgets/{widget_id}`: any
    subset of fields to update. Fields left out are left unchanged."""

    params: Optional[dict] = None
    refresh_rate: Optional[int] = None
    position: Optional[dict] = None


class WidgetInstanceOut(Schema):
    """Shape of one widget instance as returned to the frontend."""

    id: int
    service_name: str
    widget_name: str
    params: dict
    refresh_rate: int
    position: dict


@api.get("/dashboard/widgets", response=list[WidgetInstanceOut])
def list_widgets(request):
    """List every widget instance on the authenticated user's dashboard.

    Used by the frontend on load to rebuild the dashboard layout.
    """
    return WidgetInstance.objects.filter(user=request.auth)


@api.post("/dashboard/widgets", response=WidgetInstanceOut)
def create_widget(request, item: WidgetInstanceIn):
    """Add a new widget instance to the authenticated user's dashboard.

    Called once the user has picked a widget, filled in its params, refresh
    rate and position, and confirmed.
    """
    return WidgetInstance.objects.create(user=request.auth, **item.dict())


@api.patch("/dashboard/widgets/{widget_id}", response=WidgetInstanceOut)
def update_widget(request, widget_id: int, item: WidgetInstancePatch):
    """Update one of the authenticated user's widget instances.

    Only the fields provided in the request body are changed (e.g. moving a
    widget only needs `position`). Returns 404 if the widget doesn't exist
    or doesn't belong to the authenticated user.
    """
    widget = get_object_or_404(WidgetInstance, id=widget_id, user=request.auth)
    for field, value in item.dict(exclude_unset=True).items():
        setattr(widget, field, value)
    widget.save()
    return widget


@api.delete("/dashboard/widgets/{widget_id}")
def delete_widget(request, widget_id: int):
    """Remove one of the authenticated user's widget instances from the
    dashboard. Returns 404 if the widget doesn't exist or doesn't belong to
    the authenticated user.
    """
    widget = get_object_or_404(WidgetInstance, id=widget_id, user=request.auth)
    widget.delete()
    return {"message": "Widget deleted."}


class ProfileIn(Schema):
    """Expected JSON body for `POST /profile`."""

    pseudo: str
    """New display name; an empty string clears it."""


@api.get("/profile")
def get_profile(request):
    """Return the authenticated user's display name (empty if never set)."""
    profile = Profile.objects.filter(user=request.auth).first()
    return {"pseudo": profile.pseudo if profile else ""}


@api.post("/profile")
def update_profile(request, item: ProfileIn):
    """Set the authenticated user's display name.

    Returns 400 if it is longer than 50 characters.
    """
    pseudo = item.pseudo.strip()
    if len(pseudo) > 50:
        return api.create_response(
            request, {"message": "Pseudo too long (50 characters max)."}, status=400
        )
    Profile.objects.update_or_create(user=request.auth, defaults={"pseudo": pseudo})
    return {"pseudo": pseudo}


@api.delete("/account")
def delete_account(request):
    """Permanently delete the authenticated user's account and all their data
    (GDPR right to erasure — allauth has no route for it).

    Deleting the user also deletes, through `on_delete=CASCADE`: their
    widgets, profile and service tokens (services/models.py), and their email
    addresses and linked Google/GitHub accounts (allauth). The current
    session is closed first.
    """
    user = request.auth
    logout(request)
    user.delete()
    return {"message": "Account deleted."}
