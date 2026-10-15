import pytest
from django.core.exceptions import ImproperlyConfigured

from widget_hub import Service, Widget, params
from widget_hub.registry import WidgetRegistry

weather = Service("weather", description="Forecasts")


def make_widget(name="temp", service=weather, widget_params=None, **attrs):
    attrs.update(service=service, name=name, params=widget_params or [params.String("city")])
    return type(f"W_{name}", (Widget,), attrs)


@pytest.fixture
def reg():
    return WidgetRegistry()


def test_register_and_lookup(reg):
    cls = reg.register(make_widget())
    assert isinstance(reg.get("weather", "temp"), cls)
    assert reg.get("weather", "nope") is None
    assert reg.services() == [weather]
    assert len(reg) == 1


def test_register_is_usable_as_decorator(reg):
    @reg.register
    class Temp(Widget):
        service = weather
        name = "temp"

    assert reg.get("weather", "temp").__class__ is Temp


def test_registration_order_is_preserved(reg):
    reg.register(make_widget("b"))
    reg.register(make_widget("a"))
    assert [w.name for w in reg.widgets_of("weather")] == ["b", "a"]


def test_duplicate_widget_name_is_rejected_with_both_origins(reg):
    reg.register(make_widget("temp"))
    with pytest.raises(ImproperlyConfigured, match=r"Duplicate widget weather\.temp.*W_temp"):
        reg.register(make_widget("temp"))


def test_same_widget_name_in_two_services_is_allowed(reg):
    reg.register(make_widget("temp"))
    reg.register(make_widget("temp", service=Service("meteo")))
    assert len(reg) == 2


def test_duplicate_service_name_is_rejected(reg):
    reg.register(make_widget("a"))
    with pytest.raises(ImproperlyConfigured, match="Duplicate service name 'weather'"):
        reg.register(make_widget("b", service=Service("weather")))


def test_only_widget_subclasses_can_be_registered(reg):
    with pytest.raises(ImproperlyConfigured, match="expects a Widget subclass"):
        reg.register(object)


@pytest.mark.parametrize(
    ("attrs", "message"),
    [
        ({"service": "weather"}, "must be a widget_hub.Service"),
        ({"name": "Bad-Name"}, "Invalid widget"),
        ({"widget_params": ["city"]}, "only contain widget_hub.params.Param"),
        (
            {"widget_params": [params.String("x"), params.Integer("x")]},
            "parameter 'x' declared twice",
        ),
        ({"default_refresh_rate": 0}, "default_refresh_rate must be a positive integer"),
    ],
)
def test_invalid_declarations(reg, attrs, message):
    with pytest.raises(ImproperlyConfigured, match=message):
        reg.register(make_widget(**attrs))


def test_invalid_service_name():
    with pytest.raises(ImproperlyConfigured, match="Invalid service name"):
        Service("Weather API")


def test_clear(reg):
    reg.register(make_widget())
    reg.clear()
    assert len(reg) == 0 and reg.services() == []


def test_fetch_must_be_implemented(reg):
    reg.register(make_widget())
    with pytest.raises(NotImplementedError):
        reg.get("weather", "temp").fetch({}, None)
