"""One behavioural suite run against every HTTP adapter."""

import json

import pytest
from django.test import Client, override_settings

from widget_hub import WidgetError
from widget_hub.registry import registry

pytestmark = pytest.mark.django_db

ADAPTERS = {
    "ninja-session": ("/ninja/session/widgets", "session"),
    "ninja-token": ("/ninja/token/widgets", "token"),
}


class Api:
    """Small JSON client bound to one adapter mount point and auth style."""

    def __init__(self, base, auth, enforce_csrf=False):
        self.client = Client(enforce_csrf_checks=enforce_csrf)
        self.base = base
        self.auth = auth
        self.headers = {}

    def login(self, user):
        if self.auth == "session":
            self.client.force_login(user)
        else:
            self.headers = {"HTTP_AUTHORIZATION": f"Bearer {user.username}"}
        return self

    def call(self, method, path, body=None, raw=None):
        data = raw if raw is not None else (json.dumps(body) if body is not None else None)
        kwargs = {"content_type": "application/json"} if data is not None else {}
        response = getattr(self.client, method)(
            self.base + path, data=data, **kwargs, **self.headers
        )
        is_json = response.get("Content-Type", "").startswith("application/json")
        payload = json.loads(response.content) if is_json and response.content else None
        return response.status_code, payload


@pytest.fixture(params=sorted(ADAPTERS))
def adapter(request):
    return ADAPTERS[request.param]


@pytest.fixture
def alice(django_user_model):
    return django_user_model.objects.create_user("alice")


@pytest.fixture
def bob(django_user_model):
    return django_user_model.objects.create_user("bob")


@pytest.fixture
def api(adapter, alice):
    return Api(*adapter).login(alice)


def create(api, **overrides):
    body = {"service": "demo", "widget": "echo", "params": {"text": "hi"}}
    body.update(overrides)
    return api.call("post", "/instances", body)


def test_anonymous_requests_get_401(adapter):
    status, body = Api(*adapter).call("get", "/instances")
    assert status == 401
    if body is not None and "error" in body:
        assert body["error"]["code"] == "not_authenticated"


def test_catalog(api):
    status, body = api.call("get", "/catalog")
    assert status == 200
    assert {"service": "demo", "name": "echo"}.items() <= body[0].items()
    assert body[0]["params"][0]["name"] == "text"


def test_crud_roundtrip(api):
    status, created = create(api, position={"x": 1, "y": 2, "w": 3, "h": 2})
    assert status == 201
    assert created["params"] == {"text": "hi", "times": 1}
    assert created["refresh_rate"] == 300
    pk = created["id"]

    assert api.call("get", "/instances") == (200, [created])
    assert api.call("get", f"/instances/{pk}") == (200, created)

    status, updated = api.call("patch", f"/instances/{pk}", {"refresh_rate": 60})
    assert status == 200 and updated["refresh_rate"] == 60 and updated["position"]["x"] == 1

    assert api.call("delete", f"/instances/{pk}") == (204, None)
    assert api.call("get", "/instances") == (200, [])


def test_data_endpoint(api):
    pk = create(api, params={"text": "ab", "times": 2})[1]["id"]
    status, body = api.call("get", f"/instances/{pk}/data")
    assert status == 200
    assert body["data"] == {"text": "abab"} and body["cached"] is False
    assert api.call("get", f"/instances/{pk}/data")[1]["cached"] is True


def test_validation_errors_use_the_contract(api):
    status, body = create(api, params={"times": "x"}, refresh_rate=1, colour="red")
    assert status == 400
    assert body == {
        "error": {
            "code": "invalid_input",
            "message": "Invalid input.",
            "details": {"colour": "Unknown field."},
        }
    }
    status, body = create(api, params={"times": "x"}, refresh_rate=1)
    assert body["error"]["details"] == {
        "params": {"text": "This parameter is required.", "times": "Expected an integer."},
        "refresh_rate": "Must be between 30 and 86400 seconds.",
    }


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ("not json", "Request body must be valid JSON."),
        ("[1]", "Request body must be a JSON object."),
    ],
)
def test_malformed_bodies(api, raw, message):
    status, body = api.call("post", "/instances", raw=raw)
    assert status == 400
    assert body["error"]["details"] == {"__all__": message}


def test_missing_service_and_widget(api):
    status, body = api.call("post", "/instances", {})
    assert status == 400
    assert body["error"]["details"] == {
        "service": "This field is required.",
        "widget": "This field is required.",
    }


def test_unknown_widget(api):
    status, body = create(api, widget="nope")
    assert status == 400
    assert body["error"]["details"] == {"widget": "Unknown widget demo.nope."}


def test_other_users_instances_are_404(adapter, api, bob):
    other = Api(*adapter).login(bob)
    pk = create(other)[1]["id"]
    not_found = {"error": {"code": "not_found", "message": "Widget instance not found."}}
    assert api.call("get", f"/instances/{pk}") == (404, not_found)
    assert api.call("patch", f"/instances/{pk}", {"refresh_rate": 60}) == (404, not_found)
    assert api.call("delete", f"/instances/{pk}") == (404, not_found)
    assert api.call("get", f"/instances/{pk}/data") == (404, not_found)
    assert api.call("get", "/instances") == (200, [])
    assert other.call("get", f"/instances/{pk}")[0] == 200


def test_widget_errors_and_crashes(api, monkeypatch):
    echo = registry.get("demo", "echo")
    pk = create(api, params={"text": "fail"})[1]["id"]
    pk2 = create(api, params={"text": "crash"})[1]["id"]

    def fetch(self, params, context):
        if params["text"] == "fail":
            raise WidgetError("Quota exceeded.", status=429)
        raise RuntimeError("internal detail")

    monkeypatch.setattr(type(echo), "fetch", fetch)
    assert api.call("get", f"/instances/{pk}/data") == (
        429,
        {"error": {"code": "widget_error", "message": "Quota exceeded."}},
    )
    status, body = api.call("get", f"/instances/{pk2}/data")
    assert status == 503 and body["error"]["code"] == "unavailable"
    assert "internal detail" not in json.dumps(body)


def test_permission_check_hook(api):
    def deny_delete(request, owner, action):
        return action != "delete"

    pk = create(api)[1]["id"]
    with override_settings(WIDGET_HUB={"PERMISSION_CHECK": deny_delete}):
        assert api.call("delete", f"/instances/{pk}") == (
            403,
            {"error": {"code": "permission_denied", "message": "Permission denied."}},
        )
        assert api.call("get", f"/instances/{pk}")[0] == 200


def test_owner_resolver_hook(api, bob):
    pk = create(api)[1]["id"]
    with override_settings(WIDGET_HUB={"OWNER_RESOLVER": lambda request: bob}):
        assert api.call("get", f"/instances/{pk}")[0] == 404


def test_session_auth_requires_csrf_for_unsafe_methods(alice):
    base, _ = ADAPTERS["ninja-session"]
    api = Api(base, "session", enforce_csrf=True).login(alice)
    status, body = create(api)
    assert status == 403
    assert body == {"error": {"code": "permission_denied", "message": "CSRF verification failed."}}
    assert api.call("get", "/instances")[0] == 200  # safe methods are not affected

    api.client.get("/admin/login/")  # any page rendering {% csrf_token %} sets the cookie
    api.headers = {"HTTP_X_CSRFTOKEN": api.client.cookies["csrftoken"].value}
    assert create(api)[0] == 201


def test_token_auth_is_not_subject_to_csrf(alice):
    base, _ = ADAPTERS["ninja-token"]
    api = Api(base, "token", enforce_csrf=True).login(alice)
    assert create(api)[0] == 201


def test_non_integer_ids_do_not_match(api):
    assert api.call("get", "/instances/abc")[0] == 404
