"""The Epitech dashboard's 6 services and 8 widgets, declared with django-widget-hub.

This file replaces three hand-maintained places of the original backend:
``services/registry.py`` (the dict returned by /about.json), the eight data routes of
``services/api.py`` and the free-form ``WidgetInstance.params``. Names, descriptions and param
types are identical to the original registry, so /about.json is unchanged.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from widget_hub import Service, Widget, WidgetError, params, register
from widget_hub.security import safe_fetch

weather = Service("weather")
nasa_picture = Service("nasa_picture")
steam = Service("steam")
github = Service("github")
rss = Service("rss")
clock = Service("time")


def _locate(city: str) -> dict:
    """First Open-Meteo geocoding match for ``city`` (was the separate /geocode route)."""
    found = safe_fetch(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 1, "language": "fr"},
    ).json()
    if not found.get("results"):
        raise WidgetError(f"Ville introuvable : {city}", 404)
    return found["results"][0]


def _forecast(place: dict, **query) -> dict:
    response = safe_fetch(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "timezone": "auto",
            **query,
        },
    )
    if response.status != 200:
        raise WidgetError("Impossible de récupérer la météo", 503)
    return response.json()


@register
class CityTemperature(Widget):
    service = weather
    name = "city_temperature"
    description = "Display temperature and sky overview for a city"
    params = [params.String("city", min_length=1, max_length=100)]

    def fetch(self, params, context):
        place = _locate(params["city"])
        data = _forecast(
            place,
            current="temperature_2m,apparent_temperature,relative_humidity_2m,"
            "wind_speed_10m,weather_code",
        )
        current = data["current"]
        return {
            "city": place["name"],
            "latitude": data["latitude"],
            "longitude": data["longitude"],
            "temperature": current["temperature_2m"],
            "feels_like": current["apparent_temperature"],
            "humidity": current["relative_humidity_2m"],
            "wind_speed": current["wind_speed_10m"],
            "weather_code": current["weather_code"],
        }


@register
class CityForecast(Widget):
    service = weather
    name = "city_forecast"
    description = "Display the daily forecast for a city over the next days"
    params = [
        params.String("city", min_length=1, max_length=100),
        params.Integer("days", min_value=1, max_value=16, default=5),
    ]

    def fetch(self, params, context):
        daily = _forecast(
            _locate(params["city"]),
            daily="temperature_2m_max,temperature_2m_min,weather_code",
            forecast_days=params["days"],
        )["daily"]
        return {
            "days": [
                {"date": d, "temperature_max": hi, "temperature_min": lo, "weather_code": code}
                for d, hi, lo, code in zip(
                    daily["time"],
                    daily["temperature_2m_max"],
                    daily["temperature_2m_min"],
                    daily["weather_code"],
                    strict=True,
                )
            ]
        }


@register
class DailyPicture(Widget):
    service = nasa_picture
    name = "daily_picture"
    description = "Display NASA's astronomy picture from a given number of days ago"
    default_refresh_rate = 3600
    params = [params.Integer("days_ago", min_value=0, max_value=3650, default=0)]

    def fetch(self, params, context):
        # science.nasa.gov ignores date filters but returns one picture per page, newest first.
        response = safe_fetch(
            "https://science.nasa.gov/wp-json/wp/v2/apod-basic",
            params={"per_page": 1, "page": params["days_ago"] + 1},
        )
        if response.status != 200 or not response.json():
            raise WidgetError("Impossible de récupérer l'image du jour de la NASA", 503)
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


@register
class GlobalAchievements(Widget):
    service = steam
    name = "global_achievements"
    description = "Display global achievement percentages for a Steam game"
    params = [params.Integer("game_id", min_value=1)]

    def fetch(self, params, context):
        response = safe_fetch(
            "https://api.steampowered.com/ISteamUserStats/"
            "GetGlobalAchievementPercentagesForApp/v2/",
            params={"gameid": params["game_id"], "format": "json"},
        )
        if response.status != 200:
            raise WidgetError("Impossible de récupérer les données Steam", 503)
        data = response.json().get("achievementpercentages", {})
        return {"game_id": params["game_id"], "achievements": data.get("achievements", [])}


@register
class UserProfile(Widget):
    service = github
    name = "user_profile"
    description = "Display a GitHub user's profile and latest repositories"
    params = [params.String("username", min_length=1, max_length=39)]

    def fetch(self, params, context):
        headers = {"Accept": "application/vnd.github+json"}
        base = f"https://api.github.com/users/{params['username']}"
        user = safe_fetch(base, headers=headers)
        repos = safe_fetch(
            f"{base}/repos", params={"sort": "updated", "per_page": 5}, headers=headers
        )
        if user.status != 200 or repos.status != 200:
            raise WidgetError("Impossible de récupérer les données GitHub", 503)
        profile = user.json()
        return {
            "user": {
                key: profile.get(key)
                for key in (
                    "login",
                    "name",
                    "avatar_url",
                    "html_url",
                    "public_repos",
                    "followers",
                    "following",
                )
            },
            "repos": [
                {
                    key: repo.get(key)
                    for key in ("name", "html_url", "description", "language", "stargazers_count")
                }
                for repo in repos.json()
            ],
        }


@register
class RecentCommits(Widget):
    service = github
    name = "recent_commits"
    description = "Display the latest commit messages and authors of a GitHub repository"
    params = [
        params.String("owner", min_length=1, max_length=39),
        params.String("repo", min_length=1, max_length=100),
    ]
    # The user's token (if they stored one) raises the rate limit and opens private repos:
    # results then depend on the user, so they are cached per owner.
    uses_credential = True
    cache_per_owner = True

    def fetch(self, params, context):
        headers = {"Accept": "application/vnd.github+json"}
        if context.credential:
            headers["Authorization"] = f"Bearer {context.credential}"
        response = safe_fetch(
            f"https://api.github.com/repos/{params['owner']}/{params['repo']}/commits",
            params={"per_page": 10},
            headers=headers,
        )
        if response.status != 200:
            raise WidgetError("Impossible de récupérer les activités GitHub", 503)
        return {
            "owner": params["owner"],
            "repo": params["repo"],
            "commits": [
                {
                    "sha": c["sha"],
                    "author": c["commit"]["author"]["name"],
                    "message": c["commit"]["message"],
                    "date": c["commit"]["author"]["date"],
                }
                for c in response.json()
            ],
        }


@register
class ArticleList(Widget):
    service = rss
    name = "article_list"
    description = "Display the latest articles of an RSS feed"
    params = [
        params.Url("link"),
        params.Integer("number", min_value=1, max_value=20, default=5),
    ]

    def fetch(self, params, context):
        import feedparser  # already a dependency of the dashboard backend

        response = safe_fetch(params["link"], max_bytes=2_000_000)
        feed = feedparser.parse(response.content)
        if response.status != 200 or (feed.bozo and not feed.entries):
            raise WidgetError("Impossible de lire le flux RSS", 503)
        return {
            "title": feed.feed.get("title", params["link"]),
            "articles": [
                {"title": e.get("title"), "link": e.get("link"), "published": e.get("published")}
                for e in feed.entries[: params["number"]]
            ],
        }


@register
class Clock(Widget):
    service = clock
    name = "clock"
    description = "Display the current time in a given timezone"
    default_refresh_rate = 30
    params = [params.String("timezone", min_length=1, max_length=64, default="Indian/Reunion")]

    def fetch(self, params, context):
        try:
            zone = ZoneInfo(params["timezone"])
        except (ZoneInfoNotFoundError, ValueError):
            raise WidgetError(f"Fuseau horaire inconnu : {params['timezone']}", 400) from None
        now = datetime.now(zone)
        return {
            "timezone": params["timezone"],
            "iso": now.isoformat(),
            "time": now.strftime("%H:%M"),
        }
