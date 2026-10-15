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
