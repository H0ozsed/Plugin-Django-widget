"""
Database models for the `services` app.

Holds `ServiceCredential` (a user's token for a third-party service),
`WidgetInstance` (a configured widget placed on a user's dashboard) and
`Profile` (the user's display name) — the only pieces of this project's own persistent data beyond what allauth
already manages (users, sessions, email confirmations).
"""

import base64
import hashlib

from cryptography.fernet import Fernet
from django.conf import settings
from django.db import models


def _fernet():
    """Fernet (AES + HMAC) instance whose key is derived from Django's
    SECRET_KEY, so no extra key has to be configured. Changing SECRET_KEY
    makes the tokens already stored unreadable: users then re-subscribe."""
    key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_token(token):
    """Encrypt a third-party token before storing it in the database."""
    return _fernet().encrypt(token.encode()).decode()


def decrypt_token(encrypted_token):
    """Decrypt a token read from the database, to send it to the external API."""
    return _fernet().decrypt(encrypted_token.encode()).decode()


class ServiceCredential(models.Model):
    """A third-party credential a user has supplied to unlock one service.

    One row links one platform user to one external service (e.g. GitHub) via
    a personal token they provided. Widgets that require such a credential
    (see services/api.py, e.g. `github_activity`) look it up here before
    calling the external API on the user's behalf; if none is found, the
    widget calls the external API without it (public data only).

    `token` is never stored in plain text: it is written with
    `encrypt_token` and read back with `decrypt_token` (see above), so a
    leaked database dump does not expose users' tokens.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    """The platform user this credential belongs to. Deleting the user
    deletes their stored credentials too (`on_delete=CASCADE`)."""

    service_name = models.CharField(max_length=100)
    """Which service this credential is for, e.g. `"github"`. Combined with
    `user`, identifies one row — a user can have at most one credential per
    service (enforced at the application level in `github_subscribe`, via
    `update_or_create`)."""

    token = models.CharField(max_length=500)
    """The credential itself (e.g. a personal GitHub token), encrypted with
    `encrypt_token` — longer than the raw token, hence the 500 characters."""


class WidgetInstance(models.Model):
    """One configured widget placed on a user's dashboard.

    Created when a user picks a widget type, fills in its params and a
    refresh rate, then confirms — the 4-step flow the project spec requires
    (see services/api.py, the `/dashboard/widgets` endpoints). Two instances
    of the same widget (e.g. two `city_temperature` widgets for two
    different cities) are two separate rows, each with its own `params`, so
    they display independently — the spec's explicit requirement that two
    instances of the same widget show distinct information at once.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    """The owner of this dashboard widget. Deleting the user deletes their
    widget instances too."""

    service_name = models.CharField(max_length=100)
    """Which service this widget belongs to, e.g. `"weather"` — must match a
    `name` in `services.registry.SERVICES`."""

    widget_name = models.CharField(max_length=100)
    """Which widget of that service, e.g. `"city_temperature"` — must match
    a widget `name` under that service in `services.registry.SERVICES`."""

    params = models.JSONField(default=dict)
    """The values the user configured for this instance, e.g.
    `{"city": "Paris"}`. Keys/types should match the widget's declared
    `params` in the registry, though this is not yet validated against it
    (a documented improvement, not yet done)."""

    refresh_rate = models.PositiveIntegerField(default=60)
    """How often, in seconds, the frontend's Timer should re-fetch this
    widget's data. Purely a frontend concern at query time — the backend
    only stores the chosen value."""

    position = models.JSONField(default=dict)
    """Where this widget sits on the dashboard grid, e.g.
    `{"x": 0, "y": 0, "w": 2, "h": 2}` — shape left to the frontend's grid
    library, stored here opaquely so it survives a page reload."""

    created_at = models.DateTimeField(auto_now_add=True)
    """When this instance was first added to the dashboard."""


class Profile(models.Model):
    """Extra, user-editable information shown in the dashboard's navbar.

    Kept in its own table rather than on Django's `User`, whose fields are
    managed by allauth (email, username). Created on the first
    `POST /profile` — a user without a row simply has an empty pseudo.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    """The user this profile belongs to. Deleting the user deletes it too."""

    pseudo = models.CharField(max_length=50, blank=True)
    """Display name chosen by the user, shown instead of their email."""
