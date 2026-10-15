"""Owner resolution, permission check and CSRF enforcement shared by the HTTP adapters.

Both hooks are swappable through settings (dotted paths):

* ``OWNER_RESOLVER(request) -> user | None``: who owns the instances of this request.
  Default: :func:`default_owner`.
* ``PERMISSION_CHECK(request, owner, action) -> bool``: extra authorisation, called after the
  owner is resolved. ``action`` is one of :data:`ACTIONS`. Default: allow.
"""

from __future__ import annotations

from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.http import HttpRequest
from django.middleware.csrf import CsrfViewMiddleware
from django.utils.module_loading import import_string

from . import conf

ACTIONS = ("list", "create", "retrieve", "update", "delete", "fetch", "catalog")
"""Values passed as ``action`` to the permission check."""

SAFE_METHODS = ("GET", "HEAD", "OPTIONS", "TRACE")


def default_owner(request: HttpRequest) -> AbstractBaseUser | None:
    """Return the authenticated user: ``request.auth`` when an API framework set it to a user
    (django-ninja, DRF), otherwise ``request.user``; ``None`` when anonymous."""
    auth = getattr(request, "auth", None)
    if isinstance(auth, AbstractBaseUser) and auth.is_authenticated:
        return auth
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        return user
    return None


def resolve_owner(request: HttpRequest) -> AbstractBaseUser | None:
    """Call the configured ``OWNER_RESOLVER``."""
    return _hook("OWNER_RESOLVER")(request)


def has_permission(request: HttpRequest, owner: AbstractBaseUser, action: str) -> bool:
    """Call the configured ``PERMISSION_CHECK`` (allows everything when unset)."""
    check = _hook("PERMISSION_CHECK")
    return True if check is None else bool(check(request, owner, action))


def csrf_rejected(request: HttpRequest) -> bool:
    """Return True if an unsafe request authenticated by session cookie fails Django's CSRF check.

    API frameworks mark their views ``csrf_exempt``. When the owner comes from the session cookie
    (``request.user``) rather than from an API authenticator (``request.auth``), the request is
    as forgeable as a form post, so the standard CSRF check is applied here.
    """
    if request.method in SAFE_METHODS:
        return False
    if isinstance(getattr(request, "auth", None), AbstractBaseUser):
        return False  # authenticated by the API framework (token or its own CSRF-checked cookie)
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return False
    middleware = CsrfViewMiddleware(lambda r: None)  # type: ignore[arg-type,return-value]
    middleware.process_request(request)
    return middleware.process_view(request, _csrf_probe, (), {}) is not None


def _csrf_probe(request: HttpRequest) -> None:
    """Placeholder view handed to ``CsrfViewMiddleware.process_view`` (never csrf_exempt)."""


def _hook(name: str) -> Any:
    value = conf.get(name)
    return import_string(value) if isinstance(value, str) else value
