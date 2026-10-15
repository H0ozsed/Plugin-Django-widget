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
