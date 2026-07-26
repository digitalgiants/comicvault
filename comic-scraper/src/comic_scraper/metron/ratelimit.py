from __future__ import annotations

import threading
import time
from collections import deque


class RateLimiter:
    def __init__(self, max_calls: int, period_seconds: float):
        self._max_calls = max_calls
        self._period = period_seconds
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            self._evict_expired()
            if len(self._calls) >= self._max_calls:
                sleep_for = self._period - (time.monotonic() - self._calls[0])
                if sleep_for > 0:
                    time.sleep(sleep_for)
                self._evict_expired()
            self._calls.append(time.monotonic())

    def _evict_expired(self) -> None:
        now = time.monotonic()
        while self._calls and now - self._calls[0] >= self._period:
            self._calls.popleft()
