from django.apps import apps

import widget_hub


def test_app_is_installed():
    assert apps.get_app_config("widget_hub").verbose_name == "Widget Hub"


def test_version_is_defined_once():
    assert isinstance(widget_hub.__version__, str)
