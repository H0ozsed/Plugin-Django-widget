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
