# django-widget-hub

Declare a dashboard widget once in Python and get validation, caching, owner-scoped CRUD,
an `/about.json` discovery endpoint, REST adapters and a ready-made front.

> Work in progress: see [PROGRESS.md](PROGRESS.md). The full documentation lands with step 14.

## Declaring a widget

```python
# myapp/widgets.py — imported automatically at startup
from widget_hub import Service, Widget, params, register

weather = Service("weather", description="Open-Meteo forecasts")


@register
class CityForecast(Widget):
    service = weather
    name = "city_forecast"
    description = "Daily forecast for a city"
    params = [params.String("city", max_length=100), params.Integer("days", default=5)]

    def fetch(self, params, context): ...
```

Two widgets with the same `service.name` + `name`, or two `Service` objects with the same name,
stop the server at startup with an `ImproperlyConfigured` error naming both declarations.

## Params reference

| Param | Options | Accepts |
|---|---|---|
| `String(name, min_length=, max_length=)` | | strings, stripped |
| `Integer(name, min_value=, max_value=)` | | ints and decimal strings (`"42"`), not booleans or floats |
| `Boolean(name)` | | `true/false`, `"1"/"0"`, `"yes"/"no"`, `"on"/"off"` |
| `Choice(name, choices=[...])` | | one of the listed strings |
| `Url(name, schemes=("http", "https"))` | `max_length` defaults to 2048 | absolute URL with a host, no credentials |

Every param also takes `required=True`, `default=`, `label=`, `help_text=`. Defaults are validated
at declaration time. `Widget.validate(data)` returns the cleaned dict (defaults applied, optional
params without default set to `None`) or raises `ParamValidationError` whose `errors` maps each
offending parameter (or `"__all__"`) to one message, for example
`{"days": "Must be less than or equal to 16.", "colour": "Unknown parameter."}`.
`Widget.schema()` returns the JSON description used by the built-in front and API clients.

## Storage

Add `"widget_hub"` to `INSTALLED_APPS` and run `python manage.py migrate`. Each placed widget is a
`widget_hub.models.WidgetInstance` row (owner, service, widget, params, refresh_rate, position,
timestamps), editable in the Django admin where params are validated against the declaration.

## Service layer

`widget_hub.services` holds the framework-agnostic operations every adapter uses:
`list_instances(owner)`, `get_instance(owner, id)`, `create_instance(owner, service=, widget=,
params=, refresh_rate=, position=)`, `update_instance(owner, id, **fields)`,
`delete_instance(owner, id)`, `fetch_instance_data(owner, id)` and `serialize_instance(instance)`.
They raise `InvalidInput(errors)` (400) or `NotFound` (404); another user's instance is a
`NotFound`, never a 403. `fetch()` receives the validated params and a `FetchContext(owner,
instance_id)`.

## Configuration

All settings live in one dict; every key is optional and unknown keys fail `manage.py check`
(`widget_hub.E001`–`E004`).

```python
WIDGET_HUB = {
    "CACHE_ALIAS": "default",  # alias in CACHES used for fetch() results
    "CACHE_PREFIX": "widget_hub",  # prefix of every cache key
    "MIN_REFRESH_RATE": 30,  # seconds; lower refresh rates are rejected
    "MAX_REFRESH_RATE": 86400,  # seconds; higher refresh rates are rejected
    "FETCH_TIMEOUT": 10.0,  # seconds a single fetch() may run
}
```

## Caching and rate limits

`fetch()` results are cached with Django's cache framework (the `CACHE_ALIAS` backend; Django's
default is LocMem, use Redis/Memcached in production to share it between processes). The key is
`(service, widget, normalised params)`, so a hundred users showing the weather in Paris cause one
upstream call per refresh period. Set `cache_per_owner = True` on a widget whose data depends on
the user. An entry is reused while it is younger than the instance's `refresh_rate`, and refresh
rates must stay within `MIN_REFRESH_RATE`–`MAX_REFRESH_RATE`: calling the data endpoint in a loop
never reaches the external API more than once per period. Each `fetch()` runs in a worker thread
and is abandoned after `FETCH_TIMEOUT` seconds.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check . && ruff format --check .
cd example && python manage.py migrate && python manage.py runserver
```

## License

MIT, see [LICENSE](LICENSE).
