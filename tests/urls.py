"""URLconf used by the test suite."""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.urls import include, path
from ninja import NinjaAPI
from ninja.security import HttpBearer

from widget_hub.contrib import drf
from widget_hub.contrib.ninja import build_router


class BearerUsername(HttpBearer):
    """Test authenticator: the bearer token is the username."""

    def authenticate(self, request, token):
        return get_user_model().objects.filter(username=token).first()


ninja_session_api = NinjaAPI(urls_namespace="ninja_session")
ninja_session_api.add_router("/widgets", build_router())

ninja_token_api = NinjaAPI(urls_namespace="ninja_token", auth=BearerUsername())
ninja_token_api.add_router("/widgets", build_router())


def session_user(request):
    """A common ninja authenticator that trusts the session cookie without checking CSRF."""
    return request.user if request.user.is_authenticated else None


ninja_cookie_api = NinjaAPI(urls_namespace="ninja_cookie", auth=session_user)
ninja_cookie_api.add_router("/widgets", build_router())

urlpatterns = [
    path("admin/", admin.site.urls),
    path("ninja/session/", ninja_session_api.urls),
    path("ninja/token/", ninja_token_api.urls),
    path("ninja/cookie/", ninja_cookie_api.urls),
    path("drf/widgets/", include(drf.build_router().urls)),
    path("", include("widget_hub.urls")),
]
