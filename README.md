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
    "MAX_CONCURRENT_FETCHES": 32,  # running fetch() calls per process, timed-out ones included
    "ABOUT_TRUST_X_FORWARDED_FOR": False,  # /about.json client.host from X-Forwarded-For
    "OWNER_RESOLVER": "widget_hub.auth.default_owner",  # request -> user or None
    "PERMISSION_CHECK": None,  # (request, owner, action) -> bool; None allows everything
    "CREDENTIALS_KEY": None,  # secret or [new, old, ...] for the credential store; None: SECRET_KEY
    "SAFE_FETCH_TIMEOUT": 5.0,  # safe_fetch() overall deadline, seconds
    "SAFE_FETCH_MAX_BYTES": 2097152,  # safe_fetch() largest accepted body
    "SAFE_FETCH_MAX_REDIRECTS": 3,  # safe_fetch() redirects followed (each one re-validated)
}
```

`OWNER_RESOLVER` and `PERMISSION_CHECK` accept a dotted path or a callable. The default owner is
`request.auth` when an API framework set it to a user, otherwise `request.user`. `action` is one
of `catalog`, `list`, `create`, `retrieve`, `update`, `delete`, `fetch`.

## Caching and rate limits

`fetch()` results are cached with Django's cache framework (the `CACHE_ALIAS` backend; Django's
default is LocMem, use Redis/Memcached in production to share it between processes). The key is
`(service, widget, normalised params)`, so a hundred users showing the weather in Paris cause one
upstream call per refresh period. Set `cache_per_owner = True` on a widget whose data depends on
the user. An entry is reused while it is younger than the instance's `refresh_rate`, and refresh
rates must stay within `MIN_REFRESH_RATE`–`MAX_REFRESH_RATE`: calling the data endpoint in a loop
never reaches the external API more than once per period. Each `fetch()` runs in a worker thread
and is abandoned after `FETCH_TIMEOUT` seconds; at most `MAX_CONCURRENT_FETCHES` calls run at
once (abandoned ones count until they return), beyond that requests get a 503 immediately.

## Error contract

Inside `fetch()`, raise `WidgetError(message, status=502)` for expected failures: the message is
shown to the user as-is. Any other exception, a timeout or a non-JSON result becomes a 503 with a
generic message; the traceback goes to the `widget_hub` logger only. Failures are cached like
successes, so a broken upstream is retried once per refresh period, not on every request.

Every error response uses one shape:

```json
{"error": {"code": "invalid_input", "message": "Invalid input.",
           "details": {"params": {"days": "Must be less than or equal to 16."}}}}
```

| code | status | when |
|---|---|---|
| `invalid_input` | 400 | payload failed validation; `details` maps field → message |
| `not_authenticated` | 401 | no authenticated user |
| `permission_denied` | 403 | the permission check refused access |
| `not_found` | 404 | unknown widget, or instance missing or owned by someone else |
| `widget_error` | from `WidgetError` | `fetch()` raised `WidgetError` |
| `unavailable` | 503 | `fetch()` crashed, timed out, or the concurrency cap was reached |

`details` only appears for `invalid_input`.

## django-ninja adapter

```bash
pip install "django-widget-hub[ninja]"
```

```python
from ninja import NinjaAPI
from widget_hub.contrib.ninja import build_router

api = NinjaAPI(auth=...)  # your authenticators; the router inherits them
api.add_router("/widgets", build_router())
```

| Method | Path | Result |
|---|---|---|
| GET | `/widgets/catalog` | every widget's schema |
| GET | `/widgets/instances` | the user's instances |
| POST | `/widgets/instances` | create (`service`, `widget`, `params`, `refresh_rate`, `position`) → 201 |
| GET | `/widgets/instances/{id}` | one instance (404 if it is someone else's) |
| PATCH | `/widgets/instances/{id}` | update `params`, `refresh_rate`, `position` |
| DELETE | `/widgets/instances/{id}` | 204 |
| GET | `/widgets/instances/{id}/data` | `{"data": ..., "fetched_at": "...", "cached": bool}` |
| GET | `/widgets/credentials` | services the user stored a secret for (never the secret) |
| PUT | `/widgets/credentials/{service}` | store `{"secret": "..."}` encrypted → 204 |
| DELETE | `/widgets/credentials/{service}` | 204 |

Bodies are validated by widget_hub (not pydantic) so errors follow the contract above. When the
API has no authenticator and the user comes from the session cookie, unsafe methods require a
valid CSRF token; requests authenticated by a ninja authenticator are left to it. Note: when
your own ninja authenticator rejects a request, ninja answers with its own 401 body.

## DRF adapter

```bash
pip install "django-widget-hub[drf]"
```

```python
from widget_hub.contrib.drf import build_router

urlpatterns = [path("api/widgets/", include(build_router().urls))]
```

Same routes and responses as the ninja adapter (`catalog`, `instances`, `instances/{id}`,
`instances/{id}/data`; pass `build_router(trailing_slash=True)` for DRF's usual slashes). Views use
your `DEFAULT_AUTHENTICATION_CLASSES`; DRF's `SessionAuthentication` enforces CSRF for session
users and answers CSRF failures with its own `{"detail": ...}` body. Bodies must be JSON.

## Security

**Owner scoping.** Every instance and credential operation takes the owner explicitly; another
user's instance answers 404 exactly like a missing one.

**CSRF.** Unsafe requests must pass Django's CSRF check unless an API authenticator accepted the
request *and* no session cookie was sent (token clients).

**SSRF: `safe_fetch()`.** Use it whenever a URL comes from a user:

```python
from widget_hub.security import safe_fetch

response = safe_fetch(params["feed"], timeout=5, max_bytes=1_000_000)
items = parse(response.text)  # .status, .headers, .content, .text, .json()
```

It accepts only `http`/`https` URLs without embedded credentials, resolves the host and refuses it
if *any* address is private, loopback, link-local (cloud metadata), CGNAT, multicast or reserved,
including IPv4 addresses embedded in IPv6 (mapped, NAT64, 6to4, Teredo). It then connects to the
address it checked, with the original host name for `Host`, SNI and certificate validation, so DNS
rebinding cannot swap the target. Redirects are followed by hand and re-validated; the headers you
pass (API keys...) are dropped as soon as a redirect changes scheme, host or port. The deadline is
absolute: a watchdog closes the socket even if the server trickles bytes. Bodies are size-limited. Failures raise `SafeFetchError`, a `WidgetError` with a safe
message (400 refused URL, 502 network error, 504 timeout), so it can simply propagate.

**Credentials.** A widget that needs a user's API token sets `uses_credential = True` (which
requires `cache_per_owner = True`, enforced at startup) and reads `context.credential`, the
owner's secret for that widget's service only, or `None`. Users store it through
`PUT /credentials/{service}`. Secrets are encrypted with Fernet using a key derived (HKDF-SHA256)
from `CREDENTIALS_KEY`; without it, from `SECRET_KEY` with a `widget_hub.W001` warning, and
`SECRET_KEY_FALLBACKS` still decrypts after a rotation. They never appear in responses, `repr()`,
logs or the admin.

**Errors.** Exception details never reach clients (see the error contract).

## The `/about.json` endpoint

`path("", include("widget_hub.urls"))` publishes a public `GET /about.json` in the Epitech
Dashboard format, generated from the registry, so it can never disagree with the widgets that
actually exist:

```json
{"client": {"host": "10.0.0.7"},
 "server": {"current_time": 1760000000,
            "services": [{"name": "weather",
                          "widgets": [{"name": "city_forecast",
                                       "description": "Daily forecast for a city",
                                       "params": [{"name": "city", "type": "string"},
                                                  {"name": "days", "type": "integer"}]}]}]}}
```

Param types are mapped to that format's vocabulary: `Integer` → `integer`, `Boolean` →
`boolean`, everything else → `string`. `client.host` is `REMOTE_ADDR`; set
`ABOUT_TRUST_X_FORWARDED_FOR` only behind a reverse proxy that overwrites `X-Forwarded-For`,
otherwise clients could choose the value.

## Dependencies

| Package | Why |
|---|---|
| Django ≥ 5.2 | the framework this app plugs into |
| cryptography ≥ 42 | Fernet + HKDF for the credential store; the standard library has no authenticated encryption |
| django-ninja (extra `ninja`) | only for the ninja adapter |
| djangorestframework (extra `drf`) | only for the DRF adapter |

HTTP (`safe_fetch`), caching, threading and validation use the standard library and Django.

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
