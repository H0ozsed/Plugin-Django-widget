import time

import pytest
from django.test import override_settings

from widget_hub import Service, Widget, params
from widget_hub.discovery import services_document
from widget_hub.registry import WidgetRegistry


def test_about_json_is_public_and_follows_the_epitech_format(client):
    response = client.get("/about.json", REMOTE_ADDR="10.0.0.7")
    assert response.status_code == 200
    body = response.json()
    assert body["client"] == {"host": "10.0.0.7"}
    assert abs(body["server"]["current_time"] - time.time()) < 5
    assert isinstance(body["server"]["current_time"], int)
    assert body["server"]["services"] == [
        {
            "name": "demo",
            "widgets": [
                {
                    "name": "echo",
                    "description": "Echo the parameters back",
                    "params": [
                        {"name": "text", "type": "string"},
                        {"name": "times", "type": "integer"},
                    ],
                }
            ],
        }
    ]


def test_about_json_rejects_other_methods(client):
    assert client.post("/about.json").status_code == 405


def test_x_forwarded_for_is_ignored_by_default(client):
    response = client.get("/about.json", REMOTE_ADDR="10.0.0.7", HTTP_X_FORWARDED_FOR="1.2.3.4")
    assert response.json()["client"]["host"] == "10.0.0.7"


@override_settings(WIDGET_HUB={"ABOUT_TRUST_X_FORWARDED_FOR": True})
@pytest.mark.parametrize(
    ("header", "expected"), [("1.2.3.4, 10.0.0.1", "1.2.3.4"), ("", "10.0.0.7")]
)
def test_x_forwarded_for_when_trusted(client, header, expected):
    response = client.get("/about.json", REMOTE_ADDR="10.0.0.7", HTTP_X_FORWARDED_FOR=header)
    assert response.json()["client"]["host"] == expected


def test_param_types_are_mapped_to_the_epitech_vocabulary():
    reg = WidgetRegistry()
    svc = Service("types")

    @reg.register
    class AllTypes(Widget):
        service = svc
        name = "all"
        params = [
            params.String("s"),
            params.Integer("i"),
            params.Boolean("b"),
            params.Choice("c", choices=["x"]),
            params.Url("u"),
        ]

    widget_params = services_document(reg)[0]["widgets"][0]["params"]
    assert [p["type"] for p in widget_params] == [
        "string",
        "integer",
        "boolean",
        "string",
        "string",
    ]
