import pytest
from django.contrib.admin.sites import site
from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory, override_settings

from widget_hub import Service, Widget, credentials, services
from widget_hub.models import Credential
from widget_hub.registry import WidgetRegistry

pytestmark = pytest.mark.django_db


@pytest.fixture
def alice(django_user_model):
    return django_user_model.objects.create_user("alice")


def test_secret_is_encrypted_at_rest(alice):
    credentials.set_credential(alice, "vault", "ghp_supersecret")
    stored = Credential.objects.get().encrypted_secret
    assert "supersecret" not in stored
    assert credentials.get_credential(alice, "vault") == "ghp_supersecret"


def test_set_replaces_existing(alice):
    credentials.set_credential(alice, "vault", "one")
    credentials.set_credential(alice, "vault", "two")
    assert Credential.objects.count() == 1
    assert credentials.get_credential(alice, "vault") == "two"


def test_missing_and_delete(alice):
    assert credentials.get_credential(alice, "vault") is None
    assert credentials.delete_credential(alice, "vault") is False
    credentials.set_credential(alice, "vault", "x")
    assert credentials.delete_credential(alice, "vault") is True


def test_secret_never_in_repr_or_str(alice):
    credential = credentials.set_credential(alice, "vault", "ghp_supersecret")
    assert "supersecret" not in repr(credential) + str(credential)
    assert credential.encrypted_secret not in repr(credential) + str(credential)


def test_key_rotation_with_a_list_of_keys(alice):
    with override_settings(WIDGET_HUB={"CREDENTIALS_KEY": "old"}):
        credentials.set_credential(alice, "vault", "secret")
    with override_settings(WIDGET_HUB={"CREDENTIALS_KEY": ["new", "old"]}):
        assert credentials.get_credential(alice, "vault") == "secret"
    with override_settings(WIDGET_HUB={"CREDENTIALS_KEY": "new"}):
        assert credentials.get_credential(alice, "vault") is None  # old key dropped


def test_secret_key_fallback_and_its_rotation(alice):
    with override_settings(WIDGET_HUB={}, SECRET_KEY="first-secret-key"):
        credentials.set_credential(alice, "vault", "secret")
    with override_settings(
        WIDGET_HUB={}, SECRET_KEY="second-secret-key", SECRET_KEY_FALLBACKS=["first-secret-key"]
    ):
        assert credentials.get_credential(alice, "vault") == "secret"


def test_dedicated_key_differs_from_secret_key(alice):
    with override_settings(WIDGET_HUB={"CREDENTIALS_KEY": "dedicated"}):
        credentials.set_credential(alice, "vault", "secret")
    with override_settings(WIDGET_HUB={}):
        assert credentials.get_credential(alice, "vault") is None


def test_admin_never_shows_or_accepts_secrets():
    model_admin = site._registry[Credential]
    assert "encrypted_secret" not in model_admin.fields
    assert model_admin.has_add_permission(RequestFactory().get("/")) is False


def test_uses_credential_requires_cache_per_owner():
    class Leaky(Widget):
        service = Service("leaky")
        name = "leaky"
        uses_credential = True

    with pytest.raises(ImproperlyConfigured, match="must also set cache_per_owner"):
        WidgetRegistry().register(Leaky)


def test_fetch_receives_only_its_services_credential(alice):
    credentials.set_credential(alice, "demo", "not-for-vault")
    instance = services.create_instance(alice, service="vault", widget="whoami")
    assert services.fetch_instance_data(alice, instance.pk).data == {
        "has_secret": False,
        "length": 0,
    }
    credentials.set_credential(alice, "vault", "12345")
    services.update_instance(alice, instance.pk, params={"label": "again"})
    assert services.fetch_instance_data(alice, instance.pk).data == {
        "has_secret": True,
        "length": 5,
    }


def test_widgets_without_uses_credential_get_none(alice):
    credentials.set_credential(alice, "demo", "secret")
    seen = []
    echo = services.get_widget("demo", "echo")
    original = type(echo).fetch

    def spy(self, params, context):
        seen.append(context.credential)
        return original(self, params, context)

    type(echo).fetch = spy
    try:
        instance = services.create_instance(
            alice, service="demo", widget="echo", params={"text": "a"}
        )
        services.fetch_instance_data(alice, instance.pk)
    finally:
        type(echo).fetch = original
    assert seen == [None]


def test_context_repr_hides_the_credential(alice):
    context = services.FetchContext(owner=alice, instance_id=1, credential="ghp_supersecret")
    assert "supersecret" not in repr(context)
