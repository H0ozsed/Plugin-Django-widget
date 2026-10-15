"""django-ninja API of the dashboard after the migration.

Before, this module held /about.json, one route per widget, the GitHub token endpoint and the
four /dashboard/widgets CRUD routes (642 lines). They are now provided by django-widget-hub:

* ``/about.json``: ``include("widget_hub.urls")`` in ``config/urls.py``;
* widget data, CRUD and tokens: the router mounted below at ``/dashboard``.

The profile and account endpoints, unrelated to widgets, stay exactly as they were and are not
repeated in this proof. In the real project ``auth`` is ``[x_session_token_auth, django_auth]``
from allauth; this proof uses ``django_auth`` alone to avoid configuring allauth.
"""

from ninja import NinjaAPI
from ninja.security import django_auth

from widget_hub.contrib.ninja import build_router

api = NinjaAPI(auth=[django_auth])
api.add_router("/dashboard", build_router())
