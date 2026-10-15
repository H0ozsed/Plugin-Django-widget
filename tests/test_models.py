import pytest
from django.contrib.admin.sites import site
from django.core.exceptions import ValidationError
from django.core.management import call_command

from widget_hub.models import WidgetInstance

pytestmark = pytest.mark.django_db


def make(user, **kwargs):
    fields = {"service": "demo", "widget": "echo", "params": {"text": "hi"}, "refresh_rate": 60}
    fields.update(kwargs)
    return WidgetInstance(owner=user, **fields)


def test_create_and_str(django_user_model):
    user = django_user_model.objects.create_user("alice")
    instance = make(user, position={"x": 0, "y": 0, "w": 4, "h": 2})
    instance.save()
    instance.refresh_from_db()
    assert instance.position["w"] == 4
    assert str(instance) == f"demo.echo #{instance.pk} (alice)"
    assert instance.get_widget().name == "echo"
    assert list(user.widget_instances.all()) == [instance]


def test_clean_applies_defaults(django_user_model):
    instance = make(django_user_model.objects.create_user("bob"))
    instance.full_clean()
    assert instance.params == {"text": "hi", "times": 1}


def test_clean_reports_param_errors(django_user_model):
    instance = make(django_user_model.objects.create_user("bob"), params={"times": "x"})
    with pytest.raises(ValidationError) as info:
        instance.full_clean()
    assert info.value.message_dict["params"] == [
        "text: This parameter is required.",
        "times: Expected an integer.",
    ]


def test_clean_rejects_unknown_widget(django_user_model):
    instance = make(django_user_model.objects.create_user("bob"), widget="gone")
    assert instance.get_widget() is None
    with pytest.raises(ValidationError, match=r"Unknown widget demo\.gone"):
        instance.full_clean()


def test_deleting_owner_cascades(django_user_model):
    user = django_user_model.objects.create_user("carol")
    make(user).save()
    user.delete()
    assert WidgetInstance.objects.count() == 0


def test_admin_is_registered():
    assert site.is_registered(WidgetInstance)


def test_migrations_are_up_to_date():
    call_command("makemigrations", "widget_hub", "--check", "--dry-run", verbosity=0)
