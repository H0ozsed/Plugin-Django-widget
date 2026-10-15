# Integration proof: migrating the Epitech dashboard

The Epitech *Dashboard* backend (Django + django-ninja + allauth, React front) is the project
django-widget-hub was extracted from. This document migrates its widget layer to the plugin and
checks that nothing visible changes, starting with `/about.json`, which the grading script reads.

- **Original code:** `EpitechPGE3-2026/G-WEB-500-RUN-5-1-dashboard-4`, commit `e56b817`
  (2026-10-11, branch `feat/last-github-show`).
- **Where the proof lives:** in this repository under [`integration/epitech/`](../integration/epitech),
  not as a branch of the school repository (maintainer's choice, see decision D1).
  - `before/`: the original widget-related files, copied verbatim (excluded from formatting);
  - `after/`: the migrated backend (`services/widgets.py`, `services/api.py`, migrations,
    settings excerpt);
  - `about-before.json`: `/about.json` captured from the **original backend running**;
  - `capture_about.py`, `loc.py` and `tests/`: how every figure below is produced.

Reproduce:

```bash
pip install -e ".[dev]" feedparser
pytest integration/epitech --ds=epitech_after.settings   # 8 tests, also run in CI
python integration/epitech/loc.py
```

## What changed

| Original | After the migration |
|---|---|
| `services/registry.py`: 110-line dict returned by `/about.json` | removed; `/about.json` comes from `include("widget_hub.urls")` |
| `services/api.py`: `/about.json`, `/geocode`, 8 data routes, GitHub token route, 4 CRUD routes (642 lines) | `api.add_router("/dashboard", build_router())`; profile/account routes unchanged |
| `services/models.py`: `WidgetInstance`, `ServiceCredential`, `sha256(SECRET_KEY)` Fernet | rows moved to `widget_hub` by migration 0005, tables dropped by 0006; `Profile` unchanged |
| widget declarations | `services/widgets.py`: 8 `Widget` classes with typed params |
| settings | `"widget_hub"` in `INSTALLED_APPS`, `WIDGET_HUB = {"ABOUT_TRUST_X_FORWARDED_FOR": True, "POSITION_VALIDATOR": "services.legacy.pixel_position", "CREDENTIALS_KEY": ...}` |
| layout | the React front places widgets in pixels (`{x, y, width, height}`); `services/legacy.py` validates that shape instead of the built-in grid |

Names, descriptions and parameter types are the original ones, and services and widgets are
declared in the original order.

## `/about.json` before and after

`capture_about.py` calls `/about.json` with the clock frozen at `1760000000.5`, in two situations:
directly from `203.0.113.7`, and through the nginx proxy (`REMOTE_ADDR=172.20.0.1`,
`X-Forwarded-For: 198.51.100.9, 10.0.0.1`).

- **Before:** the script ran against the original backend (its own requirements, the original
  `config/settings.py` with only the database switched to SQLite), producing
  [`about-before.json`](../integration/epitech/about-before.json).
- **After:** `tests/test_about_identical.py` runs the same script against the migrated project.

Result: **byte-for-byte identical** in both situations, including key order (`json.dumps` of both
documents is equal). Two details were needed for that:

- `ABOUT_TRUST_X_FORWARDED_FOR = True`, because the original always trusted the header (it runs
  behind nginx, which overwrites it). The plugin's default is safer (`REMOTE_ADDR`), so the
  setting makes that trust explicit.
- The `link` param of `rss.article_list` is a `Url` (validated) but is published as `string`, the
  type the original used and the Epitech format knows.

## Data migration

`after/services/migrations/0005_move_widgets_to_widget_hub.py` copies the rows; 0006 drops the
old tables. `tests/test_data_migration.py` runs the real migrations (0001–0004 are the original
files, verbatim) with Django's migration executor:

- widget instances keep owner, params, refresh rate, pixel position and creation date;
- keys the old front stored in `params` but the registry never declared (`latitude`,
  `longitude`, `refresh_rate`, see `front/src/hooks/useWidjets.js`) are dropped, then params must
  pass validation; rows that cannot (e.g. `number: 99`, or a widget that never existed such as
  the `naza_picture` typo) are skipped and logged by id;
- refresh rates are brought within `MIN_REFRESH_RATE`/`MAX_REFRESH_RATE`;
- GitHub tokens are decrypted with the legacy `sha256(SECRET_KEY)` key and re-encrypted with the
  plugin's HKDF-derived key.

## Before / after

| | Before | After |
|---|---|---|
| Files touched to add one widget | 4: `registry.py`, `api.py` (route), `mywidjets.js` (params, bounds), the React component | 1: `services/widgets.py` (+ a React component only if the project keeps its own front; the built-in front needs none) |
| Widget-related lines of code (`loc.py`: no blank lines, comments, docstrings or imports) | 495 (`registry.py` 91, `api.py` 379, `models.py` 25) | 253 (`widgets.py` 232, `api.py` 2, settings 5, pixel-layout validator 14), **−49 %** |
| Duplicate service or widget name | accepted silently; two `"weather"` entries hid a widget | refused at startup with both locations |
| Registry entry without matching route (`naza_picture` vs `/nasa_picture`) | possible, found by hand | impossible: the declaration *is* the route |
| Declared widget without backend (`time.clock`) | possible (computed in React only) | impossible: every widget has a `fetch()` |
| Param validation | bounds re-coded per route (`days`, `number`, `days_ago`), stored params never checked | declared once, checked on save and before every `fetch()` |
| Error responses | `{"error": ..., "details": str(exception)}` | one contract, details only in logs |
| Upstream calls | one per user per refresh, no cache | one per (widget, params) per refresh period, cached |
| SSRF on user URLs | RSS route only; host resolved twice (rebinding window) | `safe_fetch()` everywhere, connection pinned to the checked address |
| `client.host` | always from `X-Forwarded-For` | `REMOTE_ADDR` unless explicitly trusted |
| Token encryption key | `sha256(SECRET_KEY)`: rotating the key loses every token | HKDF from a dedicated key, rotation supported |

The "after" code also does more than the original: geocoding is part of the weather widgets
(the front no longer calls `/geocode` first), and the clock has a backend.

## What the migration taught the plugin

The first version of the plugin validated positions as grid cells only. Reading the React front
during this migration showed it saves pixel positions, so every move would have failed with a
400. The plugin gained the `POSITION_VALIDATOR` setting (decision D16) instead of the project
working around it.

## What this proof does not cover

- **The React front was not migrated.** `mywidjets.js` still maps each widget to a component and
  duplicates params and bounds (`days` 1–16, `number` 1–20). With the plugin it can read them from
  `GET /dashboard/catalog` and call `GET /dashboard/instances/{id}/data` instead of one route per
  widget; components would then receive `{"data": ...}` instead of the route's body.
- **allauth is not configured in `after/`.** The real API keeps
  `auth=[x_session_token_auth, django_auth]`; the proof uses `django_auth` only.
- Live calls to the external APIs are not part of the tests (canned responses are used); the
  original endpoints were not changed.
