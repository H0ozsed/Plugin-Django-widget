import pytest
from django.core.exceptions import ImproperlyConfigured

from widget_hub import params


def test_defaults_and_label():
    p = params.Integer("days_ago")
    assert p.required and not p.has_default
    assert p.label == "Days ago"
    assert params.Integer("n", default=0).has_default


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: params.String("1city"), "Invalid parameter name"),
        (lambda: params.String("s", min_length=5, max_length=2), "min_length is greater"),
        (lambda: params.String("s", max_length=-1), "non-negative integer"),
        (lambda: params.Integer("i", min_value=3, max_value=1), "min_value is greater"),
        (lambda: params.Choice("c", choices=[]), "non-empty list of strings"),
        (lambda: params.Choice("c", choices=["a", "a"]), "duplicates"),
        (lambda: params.Url("u", schemes=()), "schemes must not be empty"),
    ],
)
def test_bad_declarations_raise(factory, message):
    with pytest.raises(ImproperlyConfigured, match=message):
        factory()


def test_type_names():
    assert [
        cls.type_name
        for cls in (params.String, params.Integer, params.Boolean, params.Choice, params.Url)
    ] == ["string", "integer", "boolean", "choice", "url"]


def test_url_has_a_default_max_length():
    assert params.Url("feed").max_length == 2048
