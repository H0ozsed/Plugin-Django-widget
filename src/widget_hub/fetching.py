"""Running ``Widget.fetch()`` with a timeout and a shared cache.

Cache entries are keyed by ``(service, widget, normalised params)`` (plus the owner id when the
widget sets ``cache_per_owner = True``), so N users displaying the same widget with the same
params trigger one upstream call per refresh period instead of N.
"""

from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from typing import Any

from django.core.cache import caches
from django.db import connections

from . import conf
from .widgets import Widget


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
    """
    cache = caches[conf.get("CACHE_ALIAS")]
    key = cache_key(widget, params, owner_id)
    entry = cache.get(key)
    now = time.time()
    if entry is not None and now - entry["fetched_at"] < max_age:
        return FetchResult(entry["data"], entry["fetched_at"], cached=True)
    data = run_with_timeout(widget, params, context, float(conf.get("FETCH_TIMEOUT")))
    json.dumps(data)  # fail before caching if fetch() returned something not JSON-serialisable
    cache.set(key, {"data": data, "fetched_at": now}, timeout=max_age)
    return FetchResult(data, now, cached=False)


def run_with_timeout(widget: Widget, params: dict[str, Any], context: Any, timeout: float) -> Any:
    """Call ``widget.fetch(params, context)`` in a worker thread, giving up after ``timeout``.

    Python cannot kill a thread: on timeout the call keeps running in the background until it
    returns, but its result is discarded. Network helpers such as ``safe_fetch`` use socket
    timeouts so such threads end on their own.
    """
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="widget_hub_fetch")
    future = executor.submit(_call_and_close_db, widget, params, context)
    try:
        return future.result(timeout=timeout)
    except FutureTimeout:
        raise FetchTimeout(
            f"{widget.service.name}.{widget.name} fetch() exceeded {timeout:g}s."
        ) from None
    finally:
        executor.shutdown(wait=False)


def _call_and_close_db(widget: Widget, params: dict[str, Any], context: Any) -> Any:
    try:
        return widget.fetch(params, context)
    finally:
        # A worker thread that touched the ORM owns its own connections: release them.
        connections.close_all()
