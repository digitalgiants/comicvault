from __future__ import annotations

from pathlib import Path


class NoDumpFoundError(FileNotFoundError):
    """Raised when the dump directory has no manually-downloaded dump to load."""


def find_latest_dump(dump_dir: Path) -> Path:
    """Finds the most recently modified GCD dump (.zip or already-extracted .db)
    in `dump_dir` -- used by `load-latest` for dumps downloaded by hand through
    a real browser and dropped into the (bind-mounted) dump directory, since
    comics.org's login page blocks automated fetches (see fetcher.py).
    """
    candidates = list(dump_dir.glob("*.zip")) + list(dump_dir.glob("*.db"))
    if not candidates:
        raise NoDumpFoundError(
            f"No .zip or .db dump files found in {dump_dir} -- download the GCD "
            "SQLite dump manually from comics.org and place it there first."
        )
    return max(candidates, key=lambda p: p.stat().st_mtime)
