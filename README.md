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

    def fetch(self, params, context):
        ...
```

Two widgets with the same `service.name` + `name`, or two `Service` objects with the same name,
stop the server at startup with an `ImproperlyConfigured` error naming both declarations.

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
