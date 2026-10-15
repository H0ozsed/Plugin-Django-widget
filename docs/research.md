# Existing solutions (researched 2026-10-15)

Need: a reusable Django app where a developer **declares** a widget (service, typed params,
`fetch()`) once in Python, and gets per-user widget instances, validation, caching, a discovery
endpoint, REST adapters and a small front, without hand-writing a registry, routes and a model.

Data below comes from the PyPI JSON API and the GitHub API on the date above. Anything not
checked is marked as such.

| Package | Last release | What it does | Why it does not fit |
|---|---|---|---|
| [django-dashing](https://github.com/talpor/django-dashing) | 0.3.4 (2019-06) | Dashing-style dashboard framework: JS widgets fed by Django views. | Single shared dashboard defined in JS; no per-user instances, no typed params, no validation. Last push 2022. |
| [django-controlcenter](https://github.com/byashimov/django-controlcenter) | 0.3.3 (2025-03) | Admin dashboards built from widget classes (charts, lists) over querysets. | Staff-facing, code-defined pages; widgets read the ORM, users cannot add/configure instances. |
| [django-admin-tools](https://github.com/django-admin-tools/django-admin-tools) | 0.9.3 (2023-08) | Customisable admin index dashboard and menu. | Admin only; modules are layout blocks, not parameterised data widgets with an API. |
| [django-jet](https://github.com/geex-arts/django-jet) | 1.0.8 (2018-10) | Admin theme with a dashboard of modules. | Admin theme; last PyPI release 2018, no support for current Django claimed on PyPI. |
| [django-plotly-dash](https://github.com/GibbsConsulting/django-plotly-dash) | 2.5.1 (2026-05) | Embeds Plotly Dash apps in Django templates. | Brings the whole Dash stack; solves "interactive chart", not "user-configured widget catalogue". |
| [django-dash](https://github.com/barseghyanartur/django-dash) | 0.6.1 (2021-03) | Per-user customisable dashboards with plugin widgets and layouts. | Closest in spirit, but form/template based, no JSON API, no discovery endpoint; PyPI classifiers list no current Django version; last push 2022. |
| [django-dashboards (wildfish)](https://github.com/wildfish/django-dashboards) | 0.1.7 (2023-12) | Declarative data dashboards with components. | Repository archived on GitHub. |
| [django-admin-charts](https://github.com/PetrDlouhy/django-admin-charts) | 1.8.0 (2026-08) | Charts over model data on the admin index. | Model statistics in the admin, not external-API widgets for end users. |
| [Wagtail admin panels](https://docs.wagtail.org/en/stable/extending/customising_admin_templates.html) | wagtail 8.0 | `construct_homepage_panels` hook adds panels to the CMS home page. | Requires Wagtail; panels are editor-facing HTML blocks, not user-configurable instances. |
| [django-dashboard-app](https://github.com/bitmazk/django-dashboard-app) | 0.2.1 (2014-04) | Grid of widget plugins polling app endpoints. | Unmaintained since 2014, shared dashboard. |

Not verified: whether any of these can be bent to cover the need with custom code; the
comparison is about what they offer out of the box, from their descriptions and READMEs.

Conclusion: none provides "declare once → validation + owner-scoped CRUD + caching + discovery
endpoint + REST adapters". `django-widget-hub` fills that gap.
