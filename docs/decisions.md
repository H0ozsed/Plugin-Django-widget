# Design decisions

Each entry: problem → options → choice → why → impact.

## D1. Where the Epitech integration proof (step 15) lives

- **Problem:** step 15 asks for a `feat/widget-plugin` branch pushed to the original dashboard
  repository, which belongs to the Epitech organisation.
- **Options:** (a) push a branch to the Epitech repo; (b) reproduce the migration inside this
  repository, reading the Epitech code only.
- **Choice:** (b), on the maintainer's instruction ("I made a repo for this project, do it here").
- **Why:** keeps the school repository untouched; the proof stays reviewable next to the plugin.
- **Impact:** the original widget-related files are copied verbatim under
  `integration/epitech/before/` (origin commit `e56b817`, excluded from formatting, no settings or
  secrets copied); `integration/epitech/after/` is the migrated backend. `/about.json` was captured
  from the original backend actually running (its own dependencies, SQLite instead of PostgreSQL)
  and the migrated project's output is compared to it in CI. The Epitech repository was only
  read, never modified or pushed to.

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

## D17. Coalescing concurrent misses and a shared worker pool

- **Problem:** measured with 20 threads asking for the same widget and params at the same
  instant on a cold cache: 20 upstream calls. Creating one executor per call also cost 259 µs.
- **Options:** (a) a distributed lock in the cache backend (needs atomic `add`, extra round
  trips, lock expiry tuning); (b) in-process "single flight"; (c) nothing, rely on the cache.
- **Choice:** (b): a dict of in-progress keys; followers wait at most `FETCH_TIMEOUT + 1` s for
  the leader's outcome and receive fresh exception objects. Workers come from one pool sized by
  `MAX_CONCURRENT_FETCHES` (slots are taken before submitting, so it never queues).
- **Why:** removes the stampede where it is cheapest; across processes the cache already limits
  the damage to one call per process.
- **Impact:** 20 → 1 upstream call, 259 → 48 µs per worker hop; no new setting.

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

## D12. `safe_fetch()` on the standard library, pinned to the checked address

- **Problem:** the Epitech RSS route checked the host with `getaddrinfo` then let `requests`
  resolve it again: a DNS answer that changes between the two (rebinding) reaches internal hosts.
- **Options:** (a) `requests` + a custom adapter; (b) `urllib3` with a resolver hook;
  (c) `http.client` with connection classes that connect to the validated IP.
- **Choice:** (c).
- **Why:** no new dependency, and pinning is a two-method override: the socket goes to the checked
  IP while `Host`, SNI and certificate validation keep the host name. All resolved addresses must
  be public (an attacker controlling DNS could otherwise mix a public and a private answer).
- **Impact:** GET only, no connection pooling, no automatic decompression: enough for widget
  feeds. Errors are `WidgetError`s with safe messages so widgets can let them propagate.
- **Review follow-up:** a security review found three gaps, fixed with regression tests:
  (1) only `Authorization` was dropped and only on host change → every caller header is now
  dropped on any origin change (scheme, host, port); (2) socket timeouts are per `recv()`, so a
  trickling server could exceed the deadline → a watchdog timer shuts the socket down at the
  absolute deadline (keeping its own socket reference, since `http.client` forgets it for
  `Connection: close` responses); (3) NAT64/6to4/Teredo addresses could encapsulate private IPv4
  → embedded IPv4 must be public too, and special ranges are rejected explicitly because
  `is_global` changed across Python versions. A further review pointed out that DNS resolution
  had no deadline (a slow authoritative server is under the URL owner's control): it now runs in
  a daemon thread joined with the remaining time; since an abandoned lookup keeps its thread until
  the system resolver gives up, pending lookups are capped by `MAX_CONCURRENT_FETCHES` (503 past
  the cap), mirroring the cap on `fetch()` threads. The TLS handshake was also suspected; a test
  trickling a TLS record shows CPython already applies the socket timeout to the whole handshake,
  so no change was made there beyond keeping that test as a guard.

## D13. Credential encryption and exposure to widgets

- **Problem:** the Epitech code used `sha256(SECRET_KEY)` directly as the Fernet key, so rotating
  `SECRET_KEY` silently destroyed every stored token, and any route could read any credential.
- **Choice:** key = HKDF-SHA256(`CREDENTIALS_KEY`, info="widget_hub.credentials.v1"); without the
  setting, `SECRET_KEY` (+ `SECRET_KEY_FALLBACKS` for decryption) and a system-check warning.
  `CREDENTIALS_KEY` may be a list for rotation (MultiFernet). Widgets only get the owner's secret
  for their own service, loaded in the request thread, and only if they set `uses_credential`,
  which requires `cache_per_owner` (startup error otherwise).
- **Impact:** a secret never crosses users through the cache, and losing the key only makes
  secrets unreadable (`None`), users then store them again.

## D14. Built-in front without a build step

- **Problem:** the front must work in any Django project without React or a bundler.
- **Options:** (a) a React/Vue bundle; (b) htmx + server-rendered fragments; (c) one vanilla JS
  file using `fetch`, `<dialog>` and CSS grid.
- **Choice:** (c), ~600 lines, ES5-style syntax that every current browser runs as is.
- **Why:** zero dependency, works with `collectstatic` only, and the JSON API it uses is the same
  contract as the ninja/DRF adapters. Pure helpers (layout, schema → form) are unit-tested with
  `node --test`; the whole flow was checked in headless Chrome during development.
- **Details:** the front's API views are `csrf_exempt` only to answer CSRF failures in the JSON
  error contract; `widget_hub.api.handle` runs Django's CSRF check on every unsafe request. Server
  data is inserted with `textContent` and only `http(s)` URLs become links or images. Overlapping
  placements are refused rather than pushing other widgets around, which keeps the logic small.
- **Design pass:** reviewed with screenshots in light, dark, loading, dialog and 390 px states.
  Icons are 24×24 stroke shapes drawn in the file (no icon font, no third-party set, so no
  licence to track); colours, spacing and shadows are `--wh-*` tokens a project can override.
  The review found a real bug: stacked on small screens, widgets kept their grid rows and
  covered each other; the script now sets `order` from the position and small screens reset rows.

## D15. Release pipeline

- **Problem:** releases must be reproducible, versioned in one place, published to TestPyPI
  without a token in the repository, and never reach the real PyPI without the maintainer.
- **Choice:** a `Release` workflow on `vX.Y.Z` tags: it checks the tag against
  `widget_hub.__version__`, builds, runs `twine check --strict` and publishes to TestPyPI with
  `pypa/gh-action-pypi-publish` and OIDC trusted publishing (`environment: testpypi`,
  `id-token: write`). The PyPI job was added once the maintainer confirmed the TestPyPI release
  (environment `pypi`, after the TestPyPI job; a manual run republishes an existing tag, whose
  name is validated before being used as a ref). CI also builds the wheel, installs it
  in a fresh virtualenv and runs the example project against it, so packaging mistakes (missing
  templates, static files or migrations) fail before a release.
- **Impact:** the TestPyPI project must be configured once with this repository, workflow
  `release.yml` and environment `testpypi` as a trusted publisher (a maintainer action). The
  README image uses an absolute URL so it renders on (Test)PyPI.

## D16. Swappable position validation

- **Problem:** the plugin validated positions as grid cells `{x, y, w, h}` (what the built-in
  front uses). Migrating the Epitech dashboard showed that its React front places widgets freely
  in pixels and saves `{x, y, width, height}`: every move would have been rejected with a 400.
- **Options:** (a) accept any JSON object (no validation); (b) support several hard-coded layout
  models; (c) a `POSITION_VALIDATOR` hook, like the owner resolver and permission check.
- **Choice:** (c), default `widget_hub.services.clean_position`.
- **Why:** positions stay validated, a project with its own front decides what a position is,
  and it costs one setting. Hook loading is shared in `conf.hook()`.
- **Impact:** the built-in front still assumes the grid; a custom validator goes with a custom
  front.

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
  A second review showed that "an authenticator accepted the request" is not enough either: the
  common ninja authenticator `lambda request: request.user` relies on the session cookie without
  checking CSRF. Final rule: the check is skipped only when an authenticator accepted the request
  **and** Django's session cookie is absent. A browser client holding both a session and a token
  must send the CSRF token; other cookie-based authenticators must check CSRF themselves.
