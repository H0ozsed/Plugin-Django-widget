import pytest
from django.core.exceptions import ImproperlyConfigured

from widget_hub import ParamValidationError, Service, Widget, params
from widget_hub.exceptions import InvalidValue
from widget_hub.params import validate_params


def ok(param, value):
    return param.clean(value)


def bad(param, value):
    with pytest.raises(InvalidValue) as info:
        param.clean(value)
    return str(info.value)


class TestString:
    def test_strips_and_bounds(self):
        p = params.String("s", min_length=2, max_length=4)
        assert ok(p, "  ab ") == "ab"
        assert bad(p, "a") == "Must be at least 2 characters long."
        assert bad(p, "abcde") == "Must be at most 4 characters long."

    def test_type(self):
        assert bad(params.String("s"), 3) == "Expected a string, got int."


class TestInteger:
    def test_accepts_ints_and_decimal_strings(self):
        p = params.Integer("i")
        assert ok(p, 3) == 3
        assert ok(p, " -12 ") == -12

    @pytest.mark.parametrize("value", [True, 1.5, "1.5", "1e3", None, "", "9" * 30])
    def test_rejects_non_integers(self, value):
        assert bad(params.Integer("i"), value) == "Expected an integer."

    def test_bounds(self):
        p = params.Integer("i", min_value=1, max_value=16)
        assert bad(p, 0) == "Must be greater than or equal to 1."
        assert bad(p, 17) == "Must be less than or equal to 16."


class TestBoolean:
    @pytest.mark.parametrize(("value", "expected"), [(True, True), ("on", True), ("0", False)])
    def test_accepted(self, value, expected):
        assert ok(params.Boolean("b"), value) is expected

    @pytest.mark.parametrize("value", [1, "maybe", None])
    def test_rejected(self, value):
        assert bad(params.Boolean("b"), value) == "Expected a boolean (true or false)."


def test_choice():
    p = params.Choice("unit", choices=["c", "f"])
    assert ok(p, "c") == "c"
    assert bad(p, "k") == "Must be one of 'c', 'f'."


class TestUrl:
    def test_valid(self):
        assert ok(params.Url("u"), "https://example.com/feed.xml") == "https://example.com/feed.xml"

    @pytest.mark.parametrize(
        ("value", "message"),
        [
            ("ftp://example.com", "URL scheme must be one of: http, https."),
            ("file:///etc/passwd", "URL scheme must be one of: http, https."),
            ("https://", "URL must include a host name."),
            ("https://user:pw@example.com", "URL must not contain credentials."),
            ("https://exa mple.com", "A URL must not contain whitespace."),
            ("http://example.com:99999", "Enter a valid URL."),
        ],
    )
    def test_invalid(self, value, message):
        assert bad(params.Url("u"), value) == message

    def test_length(self):
        assert "at most 2048" in bad(params.Url("u"), "https://a.com/" + "x" * 2048)


def test_invalid_default_is_a_declaration_error():
    with pytest.raises(ImproperlyConfigured, match="invalid default: Must be less"):
        params.Integer("days", max_value=16, default=30)


class TestValidateParams:
    declared = [
        params.String("city"),
        params.Integer("days", default=5, min_value=1),
        params.Boolean("metric", required=False),
    ]

    def test_defaults_and_optional(self):
        assert validate_params(self.declared, {"city": "Paris"}) == {
            "city": "Paris",
            "days": 5,
            "metric": None,
        }

    def test_all_errors_reported_together(self):
        with pytest.raises(ParamValidationError) as info:
            validate_params(self.declared, {"city": "   ", "days": 0, "colour": "red"})
        assert info.value.errors == {
            "colour": "Unknown parameter.",
            "city": "This parameter is required.",
            "days": "Must be greater than or equal to 1.",
        }

    @pytest.mark.parametrize("data", [[1], "x", 3])
    def test_non_object(self, data):
        with pytest.raises(ParamValidationError) as info:
            validate_params(self.declared, data)
        assert info.value.errors == {"__all__": "Parameters must be a JSON object."}

    def test_none_means_empty(self):
        with pytest.raises(ParamValidationError, match="city: This parameter is required"):
            validate_params(self.declared, None)


def test_widget_schema():
    class Forecast(Widget):
        service = Service("weather")
        name = "forecast"
        description = "Daily forecast"
        params = [
            params.String("city", max_length=100, help_text="City name"),
            params.Integer("days", min_value=1, max_value=16, default=5),
            params.Choice("unit", choices=["c", "f"], default="c"),
            params.Url("icon", required=False),
        ]

    assert Forecast.validate({"city": "Lyon"})["days"] == 5
    assert Forecast.schema() == {
        "service": "weather",
        "name": "forecast",
        "description": "Daily forecast",
        "default_refresh_rate": 300,
        "params": [
            {
                "name": "city",
                "type": "string",
                "label": "City",
                "required": True,
                "help_text": "City name",
                "max_length": 100,
            },
            {
                "name": "days",
                "type": "integer",
                "label": "Days",
                "required": False,
                "default": 5,
                "min_value": 1,
                "max_value": 16,
            },
            {
                "name": "unit",
                "type": "choice",
                "label": "Unit",
                "required": False,
                "default": "c",
                "choices": ["c", "f"],
            },
            {
                "name": "icon",
                "type": "url",
                "label": "Icon",
                "required": False,
                "max_length": 2048,
                "schemes": ["http", "https"],
            },
        ],
    }
