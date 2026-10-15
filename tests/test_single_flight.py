import threading
import time

import pytest
from django.test import override_settings

from widget_hub import Service, Widget, WidgetError, params
from widget_hub.exceptions import WidgetUnavailable
from widget_hub.fetching import cached_fetch, run_with_timeout

svc = Service("flight")


class Gate(Widget):
    """fetch() blocks until released, so concurrent callers overlap for sure."""

    service = svc
    name = "gate"
    params = [params.String("q")]

    def __init__(self, outcome=None):
        self.calls = 0
        self.started = threading.Event()
        self.release = threading.Event()
        self.outcome = outcome

    def fetch(self, params, context):
        self.calls += 1
        self.started.set()
        self.release.wait(5)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return {"q": params["q"]}


def concurrently(widget, count, **kwargs):
    """Start ``count`` cached_fetch calls; the first is the leader. Returns results/errors."""
    results, errors = [], []

    def call():
        try:
            results.append(cached_fetch(widget, {"q": "a"}, None, max_age=60, **kwargs))
        except Exception as exc:
            errors.append(exc)

    leader = threading.Thread(target=call)
    leader.start()
    assert widget.started.wait(2)
    followers = [threading.Thread(target=call) for _ in range(count - 1)]
    for t in followers:
        t.start()
    time.sleep(0.1)  # followers are now waiting on the leader's flight
    widget.release.set()
    for t in [leader, *followers]:
        t.join(5)
    return results, errors


def test_concurrent_misses_call_upstream_once():
    widget = Gate()
    results, errors = concurrently(widget, 10)
    assert widget.calls == 1 and not errors
    assert sorted(r.cached for r in results) == [False] + [True] * 9
    assert {r.fetched_at for r in results} == {results[0].fetched_at}


def test_followers_share_a_widget_error_as_distinct_exceptions():
    widget = Gate(WidgetError("Quota exceeded.", 429))
    results, errors = concurrently(widget, 5)
    assert widget.calls == 1 and not results
    assert all(isinstance(e, WidgetError) and e.status == 429 for e in errors)
    assert len({id(e) for e in errors}) == 5


def test_followers_share_a_crash_as_unavailable():
    widget = Gate(RuntimeError("boom"))
    _, errors = concurrently(widget, 4)
    assert widget.calls == 1
    assert all(isinstance(e, WidgetUnavailable) for e in errors)


def test_different_params_are_not_coalesced():
    widget = Gate()
    widget.release.set()
    cached_fetch(widget, {"q": "a"}, None, max_age=60)
    cached_fetch(widget, {"q": "b"}, None, max_age=60)
    assert widget.calls == 2


@override_settings(WIDGET_HUB={"FETCH_TIMEOUT": 0.2})
def test_followers_do_not_wait_forever():
    widget = Gate()
    started = time.monotonic()
    _, errors = concurrently(widget, 2)
    # leader times out after 0.2 s; follower gives up after FETCH_TIMEOUT + 1 s at most
    assert all(isinstance(e, WidgetUnavailable) for e in errors)
    assert time.monotonic() - started < 3


def test_worker_threads_are_reused():
    names = set()

    class Probe(Widget):
        service = svc
        name = "probe"

        def fetch(self, params, context):
            names.add(threading.current_thread().name)
            return {}

    for _ in range(20):
        run_with_timeout(Probe(), {}, None, 2)
    assert all(n.startswith("widget_hub_fetch") for n in names)
    assert len(names) < 20


@pytest.fixture(autouse=True)
def _no_leftover_flights():
    from widget_hub import fetching

    yield
    assert fetching._flights == {}
