"""
Static registry of every service and widget this backend exposes.

This is the single source of truth returned by `GET /about.json` (see
services/api.py), the endpoint the grading script uses to discover what the
application supports. Each service must have a unique "name" (two entries
sharing a name would be treated as one, silently hiding widgets — this
happened once during development and was fixed, see docs/project/CHANGELOG.md), and
every widget must declare at least one param: a widget with no configurable
parameter is invalid per the project spec and won't be counted.

Adding a new widget here does not make it work by itself — a matching route
also has to be added in services/api.py to actually serve its data, and a
matching component in the frontend (front/src/components/widgets/mywidjets.js).
"""

SERVICES = [
    {
        "name": "weather",
        "widgets": [
            {
                "name": "city_temperature",
                "description": "Display temperature and sky overview for a city",
                "params": [
                    {"name": "city", "type": "string"},
                ],
            },
            {
                "name": "city_forecast",
                "description": "Display the daily forecast for a city over the next days",
                "params": [
                    {"name": "city", "type": "string"},
                    {"name": "days", "type": "integer"},
                ],
            },
        ],
    },
    {
        "name": "nasa_picture",
        "widgets": [
            {
                "name": "daily_picture",
                "description": "Display NASA's astronomy picture from a given number of days ago",
                "params": [
                    {"name": "days_ago", "type": "integer"},
                ],
            },
        ],
    },
    {
        "name": "steam",
        "widgets": [
            {
                "name": "global_achievements",
                "description": "Display global achievement percentages for a Steam game",
                "params": [
                    {"name": "game_id", "type": "integer"},
                ],
            },
        ],
    },
    {
        "name": "github",
        "widgets": [
            {
                "name": "user_profile",
                "description": "Display a GitHub user's profile and latest repositories",
                "params": [
                    {"name": "username", "type": "string"},
                ],
            },
            {
                "name": "recent_commits",
                "description": "Display the latest commit messages and authors of a GitHub repository",
                "params": [
                    {"name": "owner", "type": "string"},
                    {"name": "repo", "type": "string"},
                ],
            },
        ],
    },
    {
        "name": "rss",
        "widgets": [
            {
                "name": "article_list",
                "description": "Display the latest articles of an RSS feed",
                "params": [
                    {"name": "link", "type": "string"},
                    {"name": "number", "type": "integer"},
                ],
            },
        ],
    },
    {
        "name": "time",
        "widgets": [
            {
                "name": "clock",
                "description": "Display the current time in a given timezone",
                "params": [
                    {"name": "timezone", "type": "string"},
                ],
            },
        ],
    },
]
"""The 6 services and 8 widgets currently implemented — see the module
docstring above for the rules each entry must follow. Returned as-is by
`GET /about.json` (see services/api.py)."""
