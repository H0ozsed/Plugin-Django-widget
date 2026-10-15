"""Keeps the figures quoted in docs/migration-epitech.md in sync with the code."""

import loc


def test_documented_line_counts():
    report = loc.report()
    assert sum(report["before"].values()) == 495
    assert sum(report["after"].values()) == 253
