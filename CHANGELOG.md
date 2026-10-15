# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
