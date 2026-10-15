# Progress

Live checklist for `django-widget-hub` (import `widget_hub`, setting `WIDGET_HUB`).
After a session restart, read this first and resume from the first unchecked step.

**Current step:** 4 — Models + migrations

## Plan (one feature = one commit = one push)

- [x] 1. Repo skeleton: pyproject (extras ninja/drf/dev), src layout, MIT, .gitignore, `example/`, pytest-django, PROGRESS.md, CI (Python/Django matrix + ruff)
- [x] 2. Core declaration API: `Widget`, `Service`, typed params (String, Integer, Boolean, Choice, Url), `@register`, registry rejecting duplicates at startup
- [x] 3. Param validation and serialisation (types, required, min/max, choices, defaults) with precise errors
- [ ] 4. Models + migrations: `WidgetInstance`, admin registration
- [ ] 5. Framework-agnostic service layer (owner-scoped CRUD, fetch data)
- [ ] 6. Caching and rate limiting (Django cache, per-call timeout, minimum refresh rate)
- [ ] 7. Error contract (`WidgetError(message, status)`, generic 503, documented JSON shape)
- [ ] 8. `/about.json` discovery endpoint (Epitech format)
- [ ] 9. django-ninja adapter
- [ ] 10. DRF adapter
- [ ] 11. Security helpers: `safe_fetch()` (SSRF) and encrypted credential store (Fernet)
- [ ] 12. Built-in front: `{% dashboard %}`, JS grid/drag/resize/settings/refresh, CSS light/dark
- [ ] 13. Example project with 3 widgets (public API, user URL via `safe_fetch`, stored credential)
- [ ] 14. Documentation and packaging (README, docs, CHANGELOG, CONTRIBUTING, build + install in fresh venv, TestPyPI release workflow)
- [ ] 15. Integration proof against the Epitech dashboard + `docs/migration-epitech.md`

## Open questions

- None blocking. Step 15 is carried out inside this repository (see `docs/decisions.md`, D1).
- Publishing to the real PyPI waits for explicit confirmation.
