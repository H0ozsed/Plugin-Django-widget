"""Encrypted per-user credential store (API tokens a user gives for one service).

Secrets are encrypted with Fernet (AES-128-CBC + HMAC-SHA256). The key is derived with
HKDF-SHA256 from ``WIDGET_HUB["CREDENTIALS_KEY"]``; when that setting is missing, from
``SECRET_KEY`` (system check warning ``widget_hub.W001``), with ``SECRET_KEY_FALLBACKS``
accepted for decryption so Django's key rotation keeps stored secrets readable.
``CREDENTIALS_KEY`` may also be a list: the first key encrypts, all keys decrypt.

Secrets never appear in ``repr()``, ``str()``, the admin or API responses.
"""

from __future__ import annotations

import base64

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser
from django.db.models import QuerySet

from . import conf
from .models import Credential

HKDF_INFO = b"widget_hub.credentials.v1"


def _derive(secret: str) -> Fernet:
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=HKDF_INFO).derive(
        secret.encode()
    )
    return Fernet(base64.urlsafe_b64encode(key))


def key_secrets() -> list[str]:
    """Secrets the Fernet keys are derived from, the encrypting one first."""
    configured = conf.get("CREDENTIALS_KEY")
    if configured:
        return [configured] if isinstance(configured, str) else list(configured)
    return [settings.SECRET_KEY, *getattr(settings, "SECRET_KEY_FALLBACKS", [])]


def _fernet() -> MultiFernet:
    return MultiFernet([_derive(secret) for secret in key_secrets()])


def encrypt(secret: str) -> str:
    """Encrypt ``secret`` for storage."""
    return _fernet().encrypt(secret.encode()).decode()


def decrypt(token: str) -> str | None:
    """Decrypt a stored value; ``None`` if no configured key can read it (key changed)."""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return None


def set_credential(owner: AbstractBaseUser, service: str, secret: str) -> Credential:
    """Store (or replace) the owner's secret for ``service``, encrypted."""
    credential, _ = Credential.objects.update_or_create(
        owner=owner, service=service, defaults={"encrypted_secret": encrypt(secret)}
    )
    return credential


def get_credential(owner: AbstractBaseUser, service: str) -> str | None:
    """Return the owner's decrypted secret for ``service``, or ``None`` if there is none."""
    credential = Credential.objects.filter(owner=owner, service=service).first()
    return None if credential is None else decrypt(credential.encrypted_secret)


def delete_credential(owner: AbstractBaseUser, service: str) -> bool:
    """Delete the owner's secret for ``service``; True if one existed."""
    deleted, _ = Credential.objects.filter(owner=owner, service=service).delete()
    return bool(deleted)


def list_credentials(owner: AbstractBaseUser) -> QuerySet[Credential]:
    """The owner's credentials (services and dates only are meant to be shown)."""
    return Credential.objects.filter(owner=owner).order_by("service")
