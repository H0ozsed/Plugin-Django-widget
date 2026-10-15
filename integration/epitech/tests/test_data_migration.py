"""End-to-end test of migrations 0005/0006: legacy rows end up in django-widget-hub."""

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from services.models import encrypt_token

from widget_hub import credentials
from widget_hub.models import Credential, WidgetInstance

pytestmark = pytest.mark.django_db(transaction=True)

LEGACY = [("services", "0004_encrypt_service_credential_token"), ("widget_hub", "0002_credential")]
LATEST = [("services", "0006_delete_legacy_widget_models")]


def migrate(targets):
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(targets)
    return executor.loader.project_state(targets).apps


def test_legacy_rows_are_moved_and_tokens_re_encrypted(django_user_model):
    old_apps = migrate(LEGACY)
    User = old_apps.get_model("auth", "User")
    OldInstance = old_apps.get_model("services", "WidgetInstance")
    OldCredential = old_apps.get_model("services", "ServiceCredential")
    alice = User.objects.create(username="alice")

    # what the old front saved (hooks/useWidjets.js): undeclared keys, pixel positions
    OldInstance.objects.create(
        user=alice,
        service_name="weather",
        widget_name="city_temperature",
        params={"city": "Paris", "latitude": 48.85, "longitude": 2.35, "refresh_rate": 5},
        refresh_rate=5,
        position={"x": 60, "y": 100, "width": 300, "height": 240},  # pixels (react-rnd)
    )
    OldInstance.objects.create(
        user=alice,
        service_name="rss",
        widget_name="article_list",
        params={"link": "https://example.com/feed.xml", "number": 7},
        refresh_rate=600,
    )
    OldInstance.objects.create(  # invalid: number out of range, cannot be kept
        user=alice,
        service_name="rss",
        widget_name="article_list",
        params={"link": "https://example.com/feed.xml", "number": 99},
        refresh_rate=60,
    )
    OldInstance.objects.create(  # widget that never existed (the "naza_picture" typo)
        user=alice,
        service_name="naza_picture",
        widget_name="daily_picture",
        params={"days_ago": 0},
        refresh_rate=60,
    )
    OldCredential.objects.create(
        user=alice, service_name="github", token=encrypt_token("ghp_legacy_token")
    )

    migrate(LATEST)

    instances = {(i.service, i.widget): i for i in WidgetInstance.objects.all()}
    assert set(instances) == {("weather", "city_temperature"), ("rss", "article_list")}
    weather = instances["weather", "city_temperature"]
    assert weather.params == {"city": "Paris"}
    assert weather.refresh_rate == 30  # raised to MIN_REFRESH_RATE
    assert weather.position == {"x": 60, "y": 100, "width": 300, "height": 240}
    assert instances["rss", "article_list"].params == {
        "link": "https://example.com/feed.xml",
        "number": 7,
    }
    assert weather.owner.username == "alice"

    stored = Credential.objects.get()
    assert "ghp_legacy_token" not in stored.encrypted_secret
    assert credentials.get_credential(stored.owner, "github") == "ghp_legacy_token"

    tables = connection.introspection.table_names()
    assert "services_widgetinstance" not in tables
    assert "services_servicecredential" not in tables
