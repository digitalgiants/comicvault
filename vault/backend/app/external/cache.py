import time
from typing import Callable, TypeVar

T = TypeVar("T")

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
