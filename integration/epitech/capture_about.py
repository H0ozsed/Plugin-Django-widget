"""Capture ``/about.json`` from a running Django project with a frozen clock.

Used for both sides of the Epitech migration so the two documents are produced the same way::

    DJANGO_SETTINGS_MODULE=<settings> python capture_about.py output.json

Two requests are recorded: one from ``203.0.113.7`` without proxy header, one through a proxy
(``X-Forwarded-For: 198.51.100.9, 10.0.0.1``). ``time.time`` is frozen at ``FROZEN_TIME``.
"""

import json
import sys
from unittest import mock

import django

FROZEN_TIME = 1760000000.5
SCENARIOS = {
    "direct": {"REMOTE_ADDR": "203.0.113.7"},
    "behind_proxy": {"REMOTE_ADDR": "172.20.0.1", "HTTP_X_FORWARDED_FOR": "198.51.100.9, 10.0.0.1"},
}


def capture() -> dict:
    """Return ``{scenario: about.json document}``."""
    django.setup()
    from django.test import Client

    client = Client()
    documents = {}
    with mock.patch("time.time", return_value=FROZEN_TIME):
        for name, meta in SCENARIOS.items():
            response = client.get("/about.json", **meta)
            if response.status_code != 200:
                raise RuntimeError(f"/about.json answered {response.status_code} ({name})")
            documents[name] = response.json()
    return documents


if __name__ == "__main__":
    with open(sys.argv[1], "w") as output:
        json.dump(capture(), output, indent=2, ensure_ascii=False)
        output.write("\n")
