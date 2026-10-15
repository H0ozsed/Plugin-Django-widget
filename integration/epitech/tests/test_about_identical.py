"""/about.json of the migrated backend is byte-for-byte the one captured from the original.

``about-before.json`` was produced by ``capture_about.py`` running the original backend
(EpitechPGE3-2026/G-WEB-500-RUN-5-1-dashboard-4 at e56b817) with SQLite; the same script runs
here against the migrated project.
"""

import json
from pathlib import Path

import capture_about

BEFORE = Path(__file__).resolve().parent.parent / "about-before.json"


def test_about_json_is_identical_to_the_original():
    after = capture_about.capture()
    before = json.loads(BEFORE.read_text())
    assert after == before
    # same key order too, i.e. the serialised documents are identical
    assert json.dumps(after) == json.dumps(before)


def test_the_eight_widgets_are_listed():
    services = capture_about.capture()["direct"]["server"]["services"]
    assert [(s["name"], len(s["widgets"])) for s in services] == [
        ("weather", 2),
        ("nasa_picture", 1),
        ("steam", 1),
        ("github", 2),
        ("rss", 1),
        ("time", 1),
    ]
