import re
from pathlib import Path

import pytest
from django.contrib.staticfiles import finders
from django.template import Context, Template
from django.test import RequestFactory, override_settings

pytestmark = pytest.mark.django_db

STATIC = Path(__file__).resolve().parent.parent / "src" / "widget_hub" / "static" / "widget_hub"


def render(user=None, title=None):
    request = RequestFactory().get("/")
    if user is not None:
        request.user = user
    else:
        from django.contrib.auth.models import AnonymousUser

        request.user = AnonymousUser()
    tag = "{% dashboard %}" if title is None else "{% dashboard title=board_title %}"
    return Template("{% load widget_hub %}" + tag).render(
        Context({"request": request, "csrf_token": "tok123", "board_title": title})
    )


def test_static_files_are_discoverable():
    assert finders.find("widget_hub/dashboard.js")
    assert finders.find("widget_hub/dashboard.css")


def test_dashboard_for_a_user_points_to_the_api(django_user_model):
    html = render(django_user_model.objects.create_user("alice"), title="My board")
    assert 'data-wh-catalog="/widget-hub/api/catalog"' in html
    assert 'data-wh-instances="/widget-hub/api/instances"' in html
    assert 'data-wh-credentials="/widget-hub/api/credentials"' in html
    assert 'data-wh-min-refresh="30"' in html and 'data-wh-max-refresh="86400"' in html
    assert 'data-wh-csrf-header="X-CSRFTOKEN"' in html
    assert 'name="csrfmiddlewaretoken" value="tok123"' in html
    assert "widget_hub/dashboard.js" in html and "widget_hub/dashboard.css" in html
    assert "My board" in html


def test_anonymous_users_get_a_message_and_no_script():
    html = render()
    assert "Log in to see your dashboard." in html
    assert "dashboard.js" not in html
    assert "data-wh-instances" not in html


@override_settings(CSRF_HEADER_NAME="HTTP_X_MY_CSRF", WIDGET_HUB={"MIN_REFRESH_RATE": 60})
def test_settings_are_reflected(django_user_model):
    html = render(django_user_model.objects.create_user("bob"))
    assert 'data-wh-csrf-header="X-MY-CSRF"' in html
    assert 'data-wh-min-refresh="60"' in html


def test_title_is_escaped(django_user_model):
    html = render(django_user_model.objects.create_user("eve"), title="<script>x</script>")
    assert "<script>x</script>" not in html


def test_no_inline_script_and_no_html_injection_in_js():
    js = (STATIC / "dashboard.js").read_text()
    assert ".innerHTML" not in js and "insertAdjacentHTML" not in js and "eval(" not in js
    html_template = (
        STATIC.parent.parent / "templates" / "widget_hub" / "dashboard.html"
    ).read_text()
    assert not re.search(r"<script(?![^>]*\bsrc=)", html_template)


def test_css_supports_light_and_dark():
    css = (STATIC / "dashboard.css").read_text()
    assert "prefers-color-scheme: dark" in css
    assert '[data-theme="dark"]' in css and '[data-theme="light"]' in css
