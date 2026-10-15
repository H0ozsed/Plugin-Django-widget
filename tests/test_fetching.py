import threading
import time

import pytest
from django.core.checks.registry import registry
from django.test import override_settings

from widget_hub import Service, Widget, fetching, params, services
from widget_hub.checks import check_settings
from widget_hub.exceptions import InvalidInput, WidgetUnavailable
from widget_hub.fetching import FetchTimeout, cache_key, cached_fetch, run_with_timeout

counter = Service("counter")


class Counting(Widget):
    """Counts upstream calls."""

    service = counter
    name = "counting"
    params = [params.String("q"), params.Integer("n", default=1)]

    def __init__(self):
        self.calls = 0

    def fetch(self, params, context):
        self.calls += 1
        return {"q": params["q"], "call": self.calls}


class PerOwner(Counting):
    name = "per_owner"
    cache_per_owner = True


class Slow(Widget):
    service = counter
    name = "slow"

    def __init__(self):
        self.release = threading.Event()

    def fetch(self, params, context):
        self.release.wait(5)
        return {}


def test_same_params_hit_the_cache():
    widget = Counting()
    first = cached_fetch(widget, {"q": "a", "n": 1}, None, max_age=60)
    second = cached_fetch(widget, {"n": 1, "q": "a"}, None, max_age=60)
    assert widget.calls == 1
    assert (first.cached, second.cached) == (False, True)
    assert second.data == first.data and second.fetched_at == first.fetched_at


def test_different_params_are_different_entries():
    widget = Counting()
    cached_fetch(widget, {"q": "a", "n": 1}, None, max_age=60)
    cached_fetch(widget, {"q": "b", "n": 1}, None, max_age=60)
    assert widget.calls == 2


def test_shared_cache_ignores_owner_by_default():
    widget = Counting()
    assert cache_key(widget, {"q": "a"}, 1) == cache_key(widget, {"q": "a"}, 2)
    cached_fetch(widget, {"q": "a"}, None, max_age=60, owner_id=1)
    cached_fetch(widget, {"q": "a"}, None, max_age=60, owner_id=2)
    assert widget.calls == 1


def test_cache_per_owner_isolates_owners():
    widget = PerOwner()
    assert cache_key(widget, {"q": "a"}, 1) != cache_key(widget, {"q": "a"}, 2)
    cached_fetch(widget, {"q": "a"}, None, max_age=60, owner_id=1)
    cached_fetch(widget, {"q": "a"}, None, max_age=60, owner_id=2)
    assert widget.calls == 2


def test_entry_older_than_callers_max_age_is_refreshed(monkeypatch):
    widget = Counting()
    cached_fetch(widget, {"q": "a"}, None, max_age=600)
    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + 120)
    assert cached_fetch(widget, {"q": "a"}, None, max_age=600).cached
    assert not cached_fetch(widget, {"q": "a"}, None, max_age=60).cached
    assert widget.calls == 2


@override_settings(
    CACHES={
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
        "widgets": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"},
    },
    WIDGET_HUB={"CACHE_ALIAS": "widgets"},
)
def test_cache_alias_is_configurable():
    widget = Counting()
    cached_fetch(widget, {"q": "a"}, None, max_age=60)
    cached_fetch(widget, {"q": "a"}, None, max_age=60)
    assert widget.calls == 2  # the dummy backend never stores anything


def test_timeout():
    widget = Slow()
    started = time.monotonic()
    with pytest.raises(FetchTimeout, match=r"counter\.slow fetch\(\) exceeded 0\.05s"):
        run_with_timeout(widget, {}, None, 0.05)
    assert time.monotonic() - started < 1
    widget.release.set()


def test_fetch_exceptions_propagate():
    class Boom(Counting):
        name = "boom"

        def fetch(self, params, context):
            raise ValueError("upstream down")

    with pytest.raises(ValueError, match="upstream down"):
        run_with_timeout(Boom(), {}, None, 1)


@override_settings(WIDGET_HUB={"FETCH_TIMEOUT": 0.05})
def test_cached_fetch_uses_timeout_setting():
    widget = Slow()
    with pytest.raises(WidgetUnavailable):
        cached_fetch(widget, {}, None, max_age=60)
    widget.release.set()


@override_settings(WIDGET_HUB={"MAX_CONCURRENT_FETCHES": 1, "FETCH_TIMEOUT": 0.05})
def test_abandoned_fetches_count_against_the_concurrency_cap():
    slow = Slow()
    with pytest.raises(FetchTimeout):
        run_with_timeout(slow, {}, None, 0.05)  # times out, thread keeps running
    with pytest.raises(WidgetUnavailable):
        run_with_timeout(Counting(), {"q": "a"}, None, 1)  # no slot left
    slow.release.set()
    deadline = time.monotonic() + 2
    while fetching.in_flight() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert run_with_timeout(Counting(), {"q": "a"}, None, 1) == {"q": "a", "call": 1}


@pytest.mark.django_db
class TestRefreshRateLimits:
    @pytest.fixture
    def user(self, django_user_model):
        return django_user_model.objects.create_user("u")

    def create(self, user, **kwargs):
        return services.create_instance(
            user, service="demo", widget="echo", params={"text": "x"}, **kwargs
        )

    @override_settings(WIDGET_HUB={"MIN_REFRESH_RATE": 60, "MAX_REFRESH_RATE": 120})
    @pytest.mark.parametrize("rate", [59, 121, "60", True])
    def test_out_of_range_rejected(self, user, rate):
        with pytest.raises(InvalidInput) as info:
            self.create(user, refresh_rate=rate)
        assert "refresh_rate" in info.value.errors

    @override_settings(WIDGET_HUB={"MIN_REFRESH_RATE": 600})
    def test_widget_default_is_raised_to_minimum(self, user):
        assert self.create(user).refresh_rate == 600

    @override_settings(WIDGET_HUB={"MAX_REFRESH_RATE": 100})
    def test_widget_default_is_lowered_to_maximum(self, user):
        assert self.create(user).refresh_rate == 100

    def test_fetch_in_a_loop_calls_upstream_once(self, user, monkeypatch):
        widget = services.get_widget("demo", "echo")
        calls = []
        original = type(widget).fetch
        monkeypatch.setattr(
            type(widget), "fetch", lambda self, p, c: calls.append(1) or original(self, p, c)
        )
        instance = self.create(user)
        results = [services.fetch_instance_data(user, instance.pk) for _ in range(5)]
        assert len(calls) == 1
        assert [r.cached for r in results] == [False, True, True, True, True]


class TestChecks:
    def ids(self):
        return [e.id for e in check_settings() if e.is_serious()]

    def test_check_is_registered(self):
        assert check_settings in registry.get_checks()

    @override_settings(WIDGET_HUB={})
    def test_missing_credentials_key_warns(self):
        assert [e.id for e in check_settings()] == ["widget_hub.W001"]

    def test_credentials_key_set_no_warning(self):
        assert [e.id for e in check_settings()] == []

    def test_default_settings_are_valid(self):
        assert self.ids() == []

    @override_settings(WIDGET_HUB={"CACHE_TIMEOUT": 3})
    def test_unknown_key(self):
        assert self.ids() == ["widget_hub.E001"]

    @override_settings(WIDGET_HUB=[])
    def test_not_a_dict(self):
        assert self.ids() == ["widget_hub.E001"]

    @override_settings(WIDGET_HUB={"MIN_REFRESH_RATE": 100, "MAX_REFRESH_RATE": 10})
    def test_inconsistent_refresh_rates(self):
        assert self.ids() == ["widget_hub.E002"]

    @override_settings(WIDGET_HUB={"FETCH_TIMEOUT": 0})
    def test_bad_timeout(self):
        assert self.ids() == ["widget_hub.E003"]

    @override_settings(WIDGET_HUB={"OWNER_RESOLVER": "no.such.function"})
    def test_unimportable_hook(self):
        assert self.ids() == ["widget_hub.E006"]

    @override_settings(WIDGET_HUB={"PERMISSION_CHECK": 42})
    def test_non_callable_hook(self):
        assert self.ids() == ["widget_hub.E006"]

    @override_settings(WIDGET_HUB={"MAX_CONCURRENT_FETCHES": 0})
    def test_bad_concurrency_cap(self):
        assert self.ids() == ["widget_hub.E005"]

    @override_settings(WIDGET_HUB={"CACHE_ALIAS": "nope"})
    def test_unknown_cache_alias(self):
        assert self.ids() == ["widget_hub.E004"]
