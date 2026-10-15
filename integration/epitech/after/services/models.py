"""Database models of the `services` app after the migration.

``WidgetInstance`` and ``ServiceCredential`` moved to django-widget-hub (``widget_hub``); their
rows are copied by migration 0005 and the tables dropped by 0006. ``Profile`` is unrelated to
widgets and unchanged. The legacy token functions remain because historical migration 0004
imports ``encrypt_token`` and 0005 needs ``decrypt_token`` to re-encrypt stored tokens.
"""

import base64
import hashlib

from cryptography.fernet import Fernet
from django.conf import settings
from django.db import models


def _fernet():
    """Legacy key: Fernet over sha256(SECRET_KEY), as before the migration."""
    key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_token(token):
    """Legacy encryption, kept for historical migration 0004."""
    return _fernet().encrypt(token.encode()).decode()


def decrypt_token(encrypted_token):
    """Legacy decryption, used by migration 0005 to move tokens to widget_hub."""
    return _fernet().decrypt(encrypted_token.encode()).decode()


class Profile(models.Model):
    """Display name shown in the dashboard's navbar (unchanged by the migration)."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    pseudo = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.pseudo or str(self.user)
