# Design decisions

Each entry: problem → options → choice → why → impact.

## D1. Where the Epitech integration proof (step 15) lives

- **Problem:** step 15 asks for a `feat/widget-plugin` branch pushed to the original dashboard
  repository, which belongs to the Epitech organisation.
- **Options:** (a) push a branch to the Epitech repo; (b) reproduce the migration inside this
  repository, reading the Epitech code only.
- **Choice:** (b), on the maintainer's instruction ("I made a repo for this project, do it here").
- **Why:** keeps the school repository untouched; the proof stays reviewable next to the plugin.
- **Impact:** the "before" code is copied verbatim under `integration/epitech/` with its origin
  commit noted; the "after" version uses the plugin, and `/about.json` is compared in tests.

## D2. Build backend and single version source

- **Problem:** the version must be defined in one place.
- **Options:** setuptools-scm (git tags), hatchling reading `__version__`, a hard-coded
  `pyproject` version.
- **Choice:** hatchling with `[tool.hatch.version] path = "src/widget_hub/__init__.py"`.
- **Why:** one line to bump, readable at runtime as `widget_hub.__version__`, no git needed to
  build an sdist.
- **Impact:** a release bumps `__version__`, adds a CHANGELOG entry and pushes tag `vX.Y.Z`.

## D3. Supported versions

- **Problem:** support the currently maintained Django versions without guessing.
- **Choice:** Django 5.2 LTS, 6.0, 6.1 (djangoproject.com/download on 2026-10-15); Python 3.10–3.14
  following the official FAQ table (5.2: 3.10–3.14, 6.0/6.1: 3.12–3.14).
- **Impact:** CI runs 11 combinations; `requires-python = ">=3.10"`, `Django>=5.2`.

## D4. How a widget declares its parameters

- **Problem:** parameter order matters (forms, `/about.json`) and parameter names must not clash
  with the widget's own attributes (`name`, `description` are common parameter names).
- **Options:** (a) class attributes `city = String()`; (b) an explicit list
  `params = [String("city")]`.
- **Choice:** (b).
- **Why:** order is explicit, no metaclass, and a parameter called `name` cannot shadow the
  widget name.
- **Impact:** the parameter name is repeated as a string; typos surface at registration time
  because names are validated.

## D5. Duplicate names fail at startup

- **Problem:** in the Epitech dashboard two services sharing a name silently hid widgets.
- **Choice:** `register()` raises `ImproperlyConfigured` with both origins; registries hold one
  `Service` object per name, so reusing a name from another `Service` instance is an error too.
  `widgets.py` modules are imported in `AppConfig.ready()` so the error happens at startup, not on
  first request.
- **Impact:** a misconfigured project does not start; tests can build isolated `WidgetRegistry()`.

## D6. A service layer below the HTTP adapters

- **Problem:** ninja, DRF and the built-in front must enforce the same owner scoping and
  validation; duplicating it per adapter is how scoping bugs appear.
- **Options:** (a) a base view class per framework; (b) plain functions taking `owner` explicitly.
- **Choice:** (b) `widget_hub.services`.
- **Why:** framework-free, trivially testable, and the owner cannot be forgotten because it is a
  required positional argument. Others' instances raise `NotFound` (→ 404) so ids cannot be probed.
- **Impact:** adapters are thin translations of exceptions to HTTP responses. Stored params are
  re-validated before `fetch()`, so a widget whose declaration changed never receives stale input.

## D7. Cache scope and freshness

- **Problem:** the plan keys the cache by (widget, params), but a widget returning user-specific
  data (private repositories via a stored token) must never serve one user's data to another.
- **Options:** (a) always per owner (safe, loses sharing); (b) always shared (efficient, leaks);
  (c) shared by default, opt-in `cache_per_owner = True`.
- **Choice:** (c). Step 11 makes credential access refuse to work unless `cache_per_owner` is set,
  so the unsafe combination cannot be written by accident.
- **Freshness:** entries store `fetched_at`; a reader accepts an entry only if it is younger than
  its own `refresh_rate`, so instances sharing params with different rates both get what they
  asked for. Non-JSON results are rejected before being cached.

## D8. Enforcing the fetch timeout

- **Problem:** a slow upstream must not block a request worker indefinitely; `fetch()` is
  arbitrary user code that may not set its own timeouts.
- **Options:** (a) trust widgets to pass timeouts; (b) `signal.alarm` (main thread, Unix only);
  (c) run `fetch()` in a worker thread and stop waiting after `FETCH_TIMEOUT`.
- **Choice:** (c), stdlib `concurrent.futures`.
- **Why:** works under any WSGI/ASGI server and OS. Threads cannot be killed, so an abandoned call
  finishes in the background; `safe_fetch()` sets socket timeouts so it always ends. Worker threads
  close their own DB connections.
- **Impact:** one short-lived thread per cache miss; documented in Limitations. A security review
  pointed out that abandoned threads were unbounded: `MAX_CONCURRENT_FETCHES` now caps running
  calls (abandoned ones included) and rejects extra calls with a 503 without caching the refusal.

## D9. Error contract

- **Problem:** the Epitech dashboard returned `{"error": ..., "details": str(exception)}`, leaking
  internal URLs and library messages, and every route had its own shape.
- **Options:** (a) let exceptions reach Django's 500 handler; (b) a single exception the widget
  author raises for user-facing errors, everything else generic.
- **Choice:** (b). `WidgetError(message, status)` is the only way to send text to the user;
  anything else is logged with its traceback and answered with a fixed 503 message.
- **Why:** widget authors decide what is safe to show; mistakes default to silence.
- **Impact:** one JSON shape `{"error": {"code", "message", "details"?}}` for every adapter.
  Failures are cached for the refresh period so a failing upstream is not retried in a loop.

## D10. `/about.json` client host and param types

- **Problem:** the Epitech code trusted `X-Forwarded-For` unconditionally (spoofable when no proxy
  overwrites it), and the format only knows a few param types.
- **Choice:** `REMOTE_ADDR` by default, `ABOUT_TRUST_X_FORWARDED_FOR` opt-in; each param class
  carries an `about_type` (`Integer` → `integer`, `Boolean` → `boolean`, others → `string`) while
  the richer `type_name` stays in `Widget.schema()`.
- **Impact:** the Epitech migration sets the flag (it runs behind nginx) to keep identical output.
  Service descriptions are not emitted, to match the format exactly.

## D11. Adapters parse bodies themselves and enforce CSRF for session users

- **Problem:** ninja validates bodies with pydantic (422, its own shape) and marks views
  `csrf_exempt`; an API without authenticator that relies on `request.user` would accept
  cross-site POSTs.
- **Options:** (a) pydantic schemas + exception handlers installed on the user's `NinjaAPI`;
  (b) adapters read the raw JSON and call `widget_hub.api`, which owns validation and CSRF.
- **Choice:** (b).
- **Why:** a router cannot install API-wide exception handlers without touching the user's API,
  and one validation path keeps every adapter's errors identical. OpenAPI still documents the
  body through `openapi_extra`.
- **Impact:** `widget_hub.api.handle()` applies `CsrfViewMiddleware` to unsafe methods unless the
  adapter reports that one of the framework's authenticators accepted the request (ninja:
  `request.auth` set; DRF: `request.successful_authenticator`). Those either use non-cookie
  credentials or enforce CSRF themselves. The first version keyed the check on where the default
  resolver found the user and skipped it entirely under DRF; a security review showed that a
  custom `OWNER_RESOLVER` reading the session bypassed it, hence the rule above (fail closed).
