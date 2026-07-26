import time

from comic_scraper.metron.ratelimit import RateLimiter


def test_allows_calls_under_the_limit_without_delay() -> None:
    limiter = RateLimiter(max_calls=5, period_seconds=1.0)
    start = time.monotonic()
    for _ in range(5):
        limiter.acquire()
    assert time.monotonic() - start < 0.1


def test_blocks_once_the_limit_is_hit_within_the_period() -> None:
    limiter = RateLimiter(max_calls=2, period_seconds=0.3)
    limiter.acquire()
    limiter.acquire()
    start = time.monotonic()
    limiter.acquire()
    assert time.monotonic() - start >= 0.25


def test_allows_calls_again_after_the_period_elapses() -> None:
    limiter = RateLimiter(max_calls=1, period_seconds=0.1)
    limiter.acquire()
    time.sleep(0.12)
    start = time.monotonic()
    limiter.acquire()
    assert time.monotonic() - start < 0.05
