import logging

import pytest

from widget_hub import Service, Widget, WidgetError, params
from widget_hub.errors import error_body, to_error_response
from widget_hub.exceptions import InvalidInput, NotFound, WidgetUnavailable
from widget_hub.fetching import cached_fetch

errors_service = Service("errors")


class Failing(Widget):
    service = errors_service
    name = "failing"
    params = [params.String("mode")]

    def __init__(self):
        self.calls = 0

    def fetch(self, params, context):
        self.calls += 1
        if params["mode"] == "expected":
            raise WidgetError("City not found.", status=404)
        if params["mode"] == "crash":
            raise RuntimeError("token=s3cr3t leaked in exception text")
        return {"when": object()}  # not JSON-serialisable


class TestWidgetError:
    def test_defaults_to_502(self):
        assert WidgetError("Upstream down").status == 502

    @pytest.mark.parametrize("status", [200, 399, 600, "404", True])
    def test_status_must_be_an_http_error(self, status):
        with pytest.raises(ValueError, match="400-599"):
            WidgetError("x", status=status)


def test_widget_error_reaches_the_client_and_is_cached():
    widget = Failing()
    for _ in range(3):
        with pytest.raises(WidgetError) as info:
            cached_fetch(widget, {"mode": "expected"}, None, max_age=60)
        assert to_error_response(info.value) == (
            404,
            {"error": {"code": "widget_error", "message": "City not found."}},
        )
    assert widget.calls == 1


@pytest.mark.parametrize("mode", ["crash", "non_json"])
def test_unexpected_failures_are_generic_503_logged_and_cached(mode, caplog):
    widget = Failing()
    for _ in range(2):
        with (
            caplog.at_level(logging.ERROR, logger="widget_hub"),
            pytest.raises(WidgetUnavailable) as info,
        ):
            cached_fetch(widget, {"mode": mode}, None, max_age=60)
        status, body = to_error_response(info.value)
        assert status == 503
        assert body == {
            "error": {
                "code": "unavailable",
                "message": "This widget is temporarily unavailable. "
                "It will retry at the next refresh.",
            }
        }
        assert "s3cr3t" not in str(body)
    assert widget.calls == 1
    assert len(caplog.records) == 1
    assert caplog.records[0].exc_info is not None  # full details are in the logs only


def test_invalid_input_shape():
    status, body = to_error_response(
        InvalidInput({"params": {"city": "This parameter is required."}})
    )
    assert status == 400
    assert body == {
        "error": {
            "code": "invalid_input",
            "message": "Invalid input.",
            "details": {"params": {"city": "This parameter is required."}},
        }
    }


def test_not_found_shape():
    assert to_error_response(NotFound("Widget instance not found.")) == (
        404,
        {"error": {"code": "not_found", "message": "Widget instance not found."}},
    )


def test_other_exceptions_are_not_mapped():
    assert to_error_response(KeyError("x")) is None


def test_error_body_omits_empty_details():
    assert error_body("not_authenticated", "Authentication required.") == {
        "error": {"code": "not_authenticated", "message": "Authentication required."}
    }
