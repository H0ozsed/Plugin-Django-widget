# Progress

Live checklist for `django-widget-hub` (import `widget_hub`, setting `WIDGET_HUB`).
After a session restart, read this first and resume from the first unchecked step.

**Current step:** all 15 steps done — waiting for the first release (see open questions).

## Plan (one feature = one commit = one push)

- [x] 1. Repo skeleton: pyproject (extras ninja/drf/dev), src layout, MIT, .gitignore, `example/`, pytest-django, PROGRESS.md, CI (Python/Django matrix + ruff)
- [x] 2. Core declaration API: `Widget`, `Service`, typed params (String, Integer, Boolean, Choice, Url), `@register`, registry rejecting duplicates at startup
- [x] 3. Param validation and serialisation (types, required, min/max, choices, defaults) with precise errors
- [x] 4. Models + migrations: `WidgetInstance`, admin registration
- [x] 5. Framework-agnostic service layer (owner-scoped CRUD, fetch data)
- [x] 6. Caching and rate limiting (Django cache, per-call timeout, minimum refresh rate)
- [x] 7. Error contract (`WidgetError(message, status)`, generic 503, documented JSON shape)
- [x] 8. `/about.json` discovery endpoint (Epitech format)
- [x] 9. django-ninja adapter
- [x] 10. DRF adapter
- [x] 11. Security helpers: `safe_fetch()` (SSRF) and encrypted credential store (Fernet)
- [x] 12. Built-in front: `{% dashboard %}`, JS grid/drag/resize/settings/refresh, CSS light/dark
- [x] 13. Example project with 3 widgets (public API, user URL via `safe_fetch`, stored credential)
- [x] 14. Documentation and packaging (README, docs, CHANGELOG, CONTRIBUTING, build + install in fresh venv, TestPyPI release workflow)
- [x] 15. Integration proof against the Epitech dashboard + `docs/migration-epitech.md`

## Open questions

- Step 15 was carried out inside this repository on the maintainer's instruction (decision D1);
  the Epitech repository was only read.
- First release `v0.1.0`: the TestPyPI trusted publisher must be configured by the maintainer
  before the tag is pushed (project `django-widget-hub`, owner `H0ozsed`, repository
  `Plugin-Django-widget`, workflow `release.yml`, environment `testpypi`). Then: bump
  `__version__` to `0.1.0`, date the CHANGELOG section, tag `v0.1.0`.
- Publishing to the real PyPI waits for explicit confirmation.
