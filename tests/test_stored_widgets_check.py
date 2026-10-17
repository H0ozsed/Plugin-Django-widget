import pytest
from django.core.checks import Tags
from django.core.checks.registry import registry
from django.core.management import call_command

from widget_hub.checks import check_stored_widgets
from widget_hub.models import WidgetInstance

pytestmark = pytest.mark.django_db


@pytest.fixture
def alice(django_user_model):
    return django_user_model.objects.create_user("alice")


def store(owner, service, widget, n=1):
    for _ in range(n):
        WidgetInstance.objects.create(owner=owner, service=service, widget=widget, refresh_rate=60)


def test_renamed_widget_is_reported_with_its_count(alice):
    store(alice, "demo", "echo")
    store(alice, "naza_picture", "daily_picture", n=2)
    messages = check_stored_widgets(databases=["default"])
    assert [(m.id, m.obj) for m in messages] == [("widget_hub.W002", "naza_picture.daily_picture")]
    assert messages[0].msg.startswith("2 widget instance(s) in database 'default'")


def test_nothing_to_report(alice):
    store(alice, "demo", "echo")
    assert check_stored_widgets(databases=["default"]) == []


def test_skipped_without_database(alice):
    store(alice, "gone", "widget")
    assert check_stored_widgets() == []


def test_registered_as_a_database_check():
    assert check_stored_widgets in registry.get_checks(include_deployment_checks=False)
    assert Tags.database in check_stored_widgets.tags


def test_runs_with_check_database(alice, capsys):
    store(alice, "gone", "widget")
    call_command("check", "--database", "default", "--tag", "database")
    assert "widget_hub.W002" in capsys.readouterr().err
