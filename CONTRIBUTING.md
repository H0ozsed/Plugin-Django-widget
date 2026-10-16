# Contributing

Thanks for helping! Issues and pull requests are welcome on
[GitHub](https://github.com/H0ozsed/Plugin-Django-widget).

## Set up

```bash
git clone https://github.com/H0ozsed/Plugin-Django-widget.git
cd Plugin-Django-widget
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

## Before opening a pull request

```bash
pytest                                                        # package tests
pytest example/demo_widgets --ds=example_project.settings     # example widgets
node --test "tests/js/*.test.js"                              # front helpers (Node >= 18)
ruff check . && ruff format --check .
cd example && python manage.py check                          # the demo still starts
```

A change is done when:

- tests cover it and everything above is green;
- public API changes are documented in `README.md` and listed under `[Unreleased]` in
  `CHANGELOG.md` ([Keep a Changelog](https://keepachangelog.com/en/1.1.0/));
- a design choice that is not obvious is recorded in `docs/decisions.md`
  (problem → options → choice → why → impact).

## Conventions

- Commits follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`,
  `docs:`, `test:`, `chore:`, `ci:`), imperative mood, with a body explaining *why* when it is
  not obvious. History is never rewritten once pushed.
- Small modules, type hints, a docstring on every public object, no new dependency without a
  justification in the README.
- Security first: owner scoping, CSRF, validation before `fetch()`, no secret or exception detail
  in responses or logs. Report vulnerabilities privately through GitHub's security advisories
  rather than public issues.

## Releasing (maintainers)

1. Bump `__version__` in `src/widget_hub/__init__.py` (the only place it is defined).
2. Move `[Unreleased]` entries in `CHANGELOG.md` under the new version with today's date.
3. Commit (`chore: release vX.Y.Z`), then `git tag vX.Y.Z && git push origin vX.Y.Z`.
4. The `Release` workflow checks the tag against `__version__`, builds, runs `twine check` and
   publishes to TestPyPI, then to PyPI, through trusted publishing (environments `testpypi` and
   `pypi`; add required reviewers to `pypi` to approve each PyPI upload by hand).
5. To (re)publish an existing tag, run the `Release` workflow manually with that tag. PyPI never
   accepts the same version twice: fix mistakes with a new version.
