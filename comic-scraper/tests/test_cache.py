import threading
from pathlib import Path

from comic_scraper.cache import LookupCache


def test_concurrent_set_for_same_key_does_not_raise(tmp_path: Path) -> None:
    cache = LookupCache(f"sqlite:///{tmp_path / 'cache.db'}")
    errors: list[Exception] = []
    barrier = threading.Barrier(2)

    def write(n: int) -> None:
        try:
            barrier.wait(timeout=5)
            cache.set("111111111111", None, {"issue_number": str(n)})
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=write, args=(n,)) for n in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert cache.get("111111111111", None) is not None
