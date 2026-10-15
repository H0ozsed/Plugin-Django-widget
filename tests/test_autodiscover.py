from widget_hub import registry


def test_widgets_module_of_installed_apps_is_autodiscovered():
    assert registry.get("demo", "echo") is not None
