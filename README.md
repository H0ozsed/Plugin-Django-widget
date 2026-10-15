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
