import time
from typing import Callable, TypeVar

T = TypeVar("T")

# tcg-scraper is stateless by design (vault/backend persists the real
# catalog) - this exists only to avoid redundant apitcg.com calls within a
# single sync run, not as a permanent cache.
_TTL_SECONDS = 15 * 60
_store: dict[str, tuple[float, object]] = {}


def cached(key: str, fetch: Callable[[], T]) -> T:
    now = time.monotonic()
    hit = _store.get(key)
    if hit is not None and now - hit[0] < _TTL_SECONDS:
        return hit[1]  # type: ignore[return-value]

    value = fetch()
    _store[key] = (now, value)
    return value
