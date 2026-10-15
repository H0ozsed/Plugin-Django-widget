"""Running ``Widget.fetch()`` with a timeout and a shared cache.

Cache entries are keyed by ``(service, widget, normalised params)`` (plus the owner id when the
widget sets ``cache_per_owner = True``), so N users displaying the same widget with the same
params trigger one upstream call per refresh period instead of N. Shared entries are visible to
every owner: a widget whose result depends on the user must set ``cache_per_owner``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from typing import Any

from django.core.cache import caches
from django.db import connections

from . import conf
from .exceptions import WidgetError, WidgetUnavailable
from .widgets import Widget

logger = logging.getLogger("widget_hub")


class FetchTimeout(Exception):
    """Raised when ``fetch()`` runs longer than ``WIDGET_HUB["FETCH_TIMEOUT"]``."""


@dataclass(frozen=True)
class FetchResult:
    """Data returned by a widget plus cache metadata.

    :ivar data: what ``fetch()`` returned.
    :ivar fetched_at: UNIX timestamp of the upstream call that produced ``data``.
    :ivar cached: whether ``data`` came from the cache.
    """

    data: Any
    fetched_at: float
    cached: bool


def cache_key(widget: Widget, params: dict[str, Any], owner_id: Any = None) -> str:
    """Return a stable, backend-safe cache key for one widget call."""
    normalised = json.dumps(params, sort_keys=True, separators=(",", ":"), default=str)
    scope = f"owner:{owner_id}" if widget.cache_per_owner else "shared"
    digest = hashlib.sha256(f"{scope}|{normalised}".encode()).hexdigest()
    return f"{conf.get('CACHE_PREFIX')}:{widget.service.name}:{widget.name}:{digest}"


def cached_fetch(
    widget: Widget,
    params: dict[str, Any],
    context: Any,
    *,
    max_age: int,
    owner_id: Any = None,
) -> FetchResult:
    """Return data at most ``max_age`` seconds old, calling ``fetch()`` only when needed.

    A fresh value is stored with ``max_age`` as timeout. Entries are compared against the
    caller's ``max_age`` too, so an instance with a short refresh rate does not get data cached
    for an instance with a longer one.

    Failures are cached for the same period, so a failing upstream is not retried more often
    than a working one: :class:`WidgetError` is re-raised as is; any other exception, a timeout
    or a non-JSON result is logged and becomes :class:`WidgetUnavailable`.

    Concurrent misses on the same key in one process are coalesced ("single flight"): the first
    caller runs ``fetch()``, the others wait for its outcome instead of calling the upstream API
    too. Across processes, the shared cache backend plays that role once the first call ends.
    """
    cache = caches[conf.get("CACHE_ALIAS")]
    key = cache_key(widget, params, owner_id)
    cached = _from_cache(cache, key, max_age)
    if cached is not None:
        return cached
    with _flights_lock:
        flight = _flights.get(key)
        leader = flight is None
        if leader:
            flight = _flights[key] = _Flight()
    if not leader:
        return flight.wait(float(conf.get("FETCH_TIMEOUT")) + 1.0)
    try:
        outcome = _fetch_and_store(cache, key, widget, params, context, max_age)
    except Exception as exc:
        flight.fail(exc)
        raise
    else:
        flight.succeed(outcome)
        return outcome
    finally:
        with _flights_lock:
            _flights.pop(key, None)


class _Flight:
    """Outcome of an in-progress ``fetch()``, shared with callers asking for the same key."""

    def __init__(self) -> None:
        self._done = threading.Event()
        self._result: FetchResult | None = None
        self._error: list[Any] | None = None

    def succeed(self, result: FetchResult) -> None:
        self._result = result
        self._done.set()

    def fail(self, exc: Exception) -> None:
        # Followers get fresh exception objects: one instance must not be raised in two threads.
        self._error = [exc.message, exc.status] if isinstance(exc, WidgetError) else None
        self._done.set()

    def wait(self, timeout: float) -> FetchResult:
        if not self._done.wait(timeout):
            raise WidgetUnavailable()
        if self._result is None:
            raise _rebuild_error(self._error)
        return FetchResult(self._result.data, self._result.fetched_at, cached=True)


_flights: dict[str, _Flight] = {}
_flights_lock = threading.Lock()


def _from_cache(cache: Any, key: str, max_age: int) -> FetchResult | None:
    entry = cache.get(key)
    if entry is None or time.time() - entry["fetched_at"] >= max_age:
        return None
    if "error" in entry:
        raise _rebuild_error(entry["error"])
    return FetchResult(entry["data"], entry["fetched_at"], cached=True)


def _fetch_and_store(
    cache: Any, key: str, widget: Widget, params: dict[str, Any], context: Any, max_age: int
) -> FetchResult:
    now = time.time()
    label = f"{widget.service.name}.{widget.name}"
    try:
        data = run_with_timeout(widget, params, context, float(conf.get("FETCH_TIMEOUT")))
        json.dumps(data)
    except WidgetError as exc:
        cache.set(key, {"error": [exc.message, exc.status], "fetched_at": now}, timeout=max_age)
        raise
    except WidgetUnavailable:
        raise  # concurrency cap reached: transient, not cached
    except FetchTimeout as exc:
        logger.warning("widget_hub: %s", exc)
        cache.set(key, {"error": None, "fetched_at": now}, timeout=max_age)
        raise WidgetUnavailable() from None
    except Exception:
        logger.exception("widget_hub: %s fetch() failed", label)
        cache.set(key, {"error": None, "fetched_at": now}, timeout=max_age)
        raise WidgetUnavailable() from None
    cache.set(key, {"data": data, "fetched_at": now}, timeout=max_age)
    return FetchResult(data, now, cached=False)


def _rebuild_error(stored: list[Any] | None) -> Exception:
    if stored is None:
        return WidgetUnavailable()
    message, status = stored
    return WidgetError(message, status)


def run_with_timeout(widget: Widget, params: dict[str, Any], context: Any, timeout: float) -> Any:
    """Call ``widget.fetch(params, context)`` in a worker thread, giving up after ``timeout``.

    Python cannot kill a thread: on timeout the call keeps running in the background until it
    returns, but its result is discarded. Network helpers such as ``safe_fetch`` use socket
    timeouts so such threads end on their own. Running calls, abandoned ones included, are
    capped by ``MAX_CONCURRENT_FETCHES``; past the cap :class:`WidgetUnavailable` is raised at
    once, so a slow upstream cannot make the process accumulate threads.
    """
    if not _acquire_slot(conf.get("MAX_CONCURRENT_FETCHES")):
        logger.warning(
            "widget_hub: %s.%s rejected, MAX_CONCURRENT_FETCHES reached",
            widget.service.name,
            widget.name,
        )
        raise WidgetUnavailable()
    try:
        future = _executor().submit(_call_in_worker, widget, params, context)
    except BaseException:
        _release_slot()
        raise
    try:
        return future.result(timeout=timeout)
    except FutureTimeout:
        raise FetchTimeout(
            f"{widget.service.name}.{widget.name} fetch() exceeded {timeout:g}s."
        ) from None


_pool: ThreadPoolExecutor | None = None
_pool_size = 0
_pool_lock = threading.Lock()


def _executor() -> ThreadPoolExecutor:
    """The shared worker pool, as large as ``MAX_CONCURRENT_FETCHES``.

    Slots are taken before submitting, so the pool never queues work behind abandoned calls.
    If the setting grows, a larger pool replaces it (running calls finish in the old one).
    """
    global _pool, _pool_size
    size = conf.get("MAX_CONCURRENT_FETCHES")
    with _pool_lock:
        if _pool is None or size > _pool_size:
            old = _pool
            _pool = ThreadPoolExecutor(max_workers=size, thread_name_prefix="widget_hub_fetch")
            _pool_size = size
            if old is not None:
                old.shutdown(wait=False)
        return _pool


_in_flight = 0
_in_flight_lock = threading.Lock()


def in_flight() -> int:
    """Number of ``fetch()`` calls currently running, abandoned ones included."""
    return _in_flight


def _acquire_slot(limit: int) -> bool:
    global _in_flight
    with _in_flight_lock:
        if _in_flight >= limit:
            return False
        _in_flight += 1
        return True


def _release_slot() -> None:
    global _in_flight
    with _in_flight_lock:
        _in_flight -= 1


def _call_in_worker(widget: Widget, params: dict[str, Any], context: Any) -> Any:
    try:
        return widget.fetch(params, context)
    finally:
        _release_slot()
        # A worker thread that touched the ORM owns its own connections: release them.
        connections.close_all()
