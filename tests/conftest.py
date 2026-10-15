import pytest
from django.core.cache import caches


@pytest.fixture(autouse=True)
def _clear_caches():
    yield
    for cache in caches.all():
        cache.clear()
