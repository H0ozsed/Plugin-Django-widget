"""Test-only DRF authenticator: ``Authorization: Bearer <username>``."""

from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication


class BearerUsername(BaseAuthentication):
    """Authenticates the user whose username is the bearer token; the token is ``request.auth``."""

    def authenticate(self, request):
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if not header.startswith("Bearer "):
            return None
        token = header.removeprefix("Bearer ")
        user = get_user_model().objects.filter(username=token).first()
        return (user, token) if user else None

    def authenticate_header(self, request):
        return "Bearer"
