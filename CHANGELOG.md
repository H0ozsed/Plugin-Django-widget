# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-10-16

First release.

### Added

- Project skeleton: src layout, `widget_hub` app config, pytest-django test suite, demo project
  under `example/`, CI on Django 5.2 / 6.0 / 6.1 with every Python version each one supports.
- Declaration API: `Service`, `Widget`, typed params (`String`, `Integer`, `Boolean`, `Choice`,
  `Url`), `@register`, and a registry that refuses duplicate service or widget names at startup.
  `<app>/widgets.py` modules are autodiscovered.
- Parameter validation (`Widget.validate`, `ParamValidationError`) with per-field messages,
  defaults, bounds, choices, URL checks, unknown-key rejection; `Widget.schema()` for clients.
- `WidgetInstance` model (owner via `AUTH_USER_MODEL`, service, widget, params, refresh rate,
  position, timestamps), its initial migration and admin; `clean()` validates params.
- Framework-agnostic service layer (`widget_hub.services`): owner-scoped list/get/create/update/
  delete, `fetch_instance_data`, `FetchContext`, `InvalidInput` and `NotFound` exceptions.
- `WIDGET_HUB` settings dict with system checks; `fetch()` results cached per
  (widget, normalised params) through Django's cache framework, `Widget.cache_per_owner`,
  `MIN_REFRESH_RATE`/`MAX_REFRESH_RATE` enforcement and a per-call `FETCH_TIMEOUT`.
- Error contract: `WidgetError(message, status)`, generic 503 for crashes/timeouts with details
  only in logs, cached failures, one JSON error shape (`widget_hub.errors`).
- `MAX_CONCURRENT_FETCHES` caps running `fetch()` calls, timed-out ones included, so a slow
  upstream cannot make the process accumulate threads.
- Public `GET /about.json` (Epitech Dashboard format) generated from the registry, via
  `include("widget_hub.urls")`; `ABOUT_TRUST_X_FORWARDED_FOR` setting.
- django-ninja adapter `widget_hub.contrib.ninja.build_router()`; shared HTTP operations in
  `widget_hub.api`; swappable `OWNER_RESOLVER` and `PERMISSION_CHECK`; CSRF enforced for
  cookie-authenticated unsafe requests reaching CSRF-exempt API views.
- DRF adapter `widget_hub.contrib.drf.build_router()` (`CatalogViewSet`, `WidgetInstanceViewSet`)
  with the same routes, responses and error contract as the ninja adapter.
- `widget_hub.security.safe_fetch()`: SSRF-safe GET (public addresses only, connection pinned to
  the checked address, re-validated redirects, timeout, size limit) raising `SafeFetchError`.
- Encrypted credential store (`Credential` model, `widget_hub.credentials`, Fernet with an
  HKDF-derived key from `CREDENTIALS_KEY` or `SECRET_KEY`), `Widget.uses_credential`,
  `FetchContext.credential`, `/credentials` endpoints in both adapters, warning `widget_hub.W001`.
- New dependency: `cryptography`.
- Built-in front: `{% load widget_hub %}{% dashboard %}` template tag, dependency-free
  `dashboard.js` (grid, pointer and keyboard move/resize without overlaps, settings forms
  generated from the param schema, per-widget errors with retry, refresh paused on hidden tabs,
  `WidgetHub.registerRenderer`), `dashboard.css` with light/dark themes, and a session-authenticated
  JSON API under `widget-hub/api/` in `widget_hub.urls`. `Widget.schema()` exposes
  `uses_credential`.
- Example project: weather (public API), RSS (user URL through `safe_fetch`, DTDs refused) and
  GitHub (stored token) widgets with custom renderers and tests.
- `POSITION_VALIDATOR` setting: position validation is swappable for fronts that do not use the
  built-in grid (found while migrating the Epitech dashboard, whose React front stores pixels).
- Documentation: full README, CONTRIBUTING, research notes, design decisions.
- Integration proof (`integration/epitech/`, `docs/migration-epitech.md`): the Epitech dashboard's
  widget layer migrated to the plugin with an identical `/about.json`, a tested data migration and
  reproducible line counts.
- Packaging: CI job installing the built wheel in a fresh virtualenv and running the example
  against it; `Release` workflow publishing tags to TestPyPI through trusted publishing.

### Changed

- Built-in front design pass: consistent SVG icons, ghost icon buttons with hover/active states,
  loading placeholders, params summary under each title, relative "Updated … ago" times, error
  cards with "Try again", empty state with a call to action, dialog with a close button and
  widgets grouped by service, spacing and shadow tokens, 44 px touch targets, reduced-motion
  support. New widgets default to 3 rows so their content fits.
- The generic 503 message is now "This widget is temporarily unavailable." (the server no longer
  promises client behaviour; the front says it retries).

### Fixed

- On small screens, widgets kept their grid rows while stacked in one column and covered each
  other (only 2 of 4 widgets were visible); they now stack in reading order.

### Performance

- Concurrent cache misses on the same widget and params are coalesced ("single flight"):
  20 simultaneous identical requests now make 1 upstream call instead of 20.
- `fetch()` runs in a shared worker pool instead of a new executor per call (worker hop
  259 µs → 48 µs median).

### Security

- CSRF is now enforced on unsafe requests whenever no framework authenticator accepted the
  request (previously the DRF adapter skipped the check entirely, so a custom `OWNER_RESOLVER`
  reading Django's session could be driven cross-site).
- CSRF is also enforced when a framework authenticator accepted the request but the browser sent
  Django's session cookie: ninja authenticators that simply return `request.user` no longer
  bypass it. Only requests without the session cookie (token clients) skip the check.
- `safe_fetch()` hardening: IPv4 addresses embedded in IPv6 (NAT64, 6to4, Teredo) must be public;
  special ranges are rejected explicitly on every Python version; caller headers (not only
  `Authorization`) are dropped on any cross-origin redirect, including https→http on the same
  host; the deadline is enforced by a watchdog so a server trickling bytes cannot hold the call.
- `safe_fetch()` DNS resolution is bounded by the remaining deadline: `getaddrinfo` has no timeout
  and a slow authoritative DNS server, chosen by whoever controls the URL, extended every hop.
  Pending lookups, abandoned ones included, are capped by `MAX_CONCURRENT_FETCHES`.

[Unreleased]: https://github.com/H0ozsed/Plugin-Django-widget/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/H0ozsed/Plugin-Django-widget/releases/tag/v0.1.0
