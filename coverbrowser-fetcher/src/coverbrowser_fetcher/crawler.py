from __future__ import annotations

import html as html_module
import logging
import re
import time
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://www.coverbrowser.com"

# coverbrowser's own master index is split into 27 letter pages - see /a-z.
INDEX_BUCKETS = ["0-9"] + list("abcdefghijklmnopqrstuvwxyz")

# Only these two path shapes are ever requested - built entirely from our own
# crawled slugs, never from user input. robots.txt disallows /search, /tag/,
# /collections, /lab/, /temp/, /colorsearch - none of which this code ever
# constructs, so there's no separate runtime allowlist check needed.

# One row per series on an /a-z/<bucket> page:
#   <p><a href="/covers/badger">Badger</a> <span class="footnote">(70)</span></p>
#   <p><a href="/covers/babe"><img src="/image/icons/dark-horse.png" alt="" /> Babe</a> <span class="footnote">(4)</span></p>
_INDEX_ENTRY_RE = re.compile(
    r'<p><a href="/covers/([a-z0-9-]+)">(?:<img[^>]*/>\s*)?([^<]+)</a>\s*'
    r'(?:<span class="footnote">\((\d+)\)</span>)?</p>'
)

# One cover on a series page:
#   <p class="cover" id="cover190476"><a name="i1"></a><br /><img src="/image/badaxe/1-1.jpg" alt="Badaxe 1" .../>...
_COVER_ENTRY_RE = re.compile(
    r'<p class="cover"[^>]*><a name="i([^"]+)"></a>.*?<img src="(/image/[^"]+)"',
    re.S,
)
_SERIES_TITLE_RE = re.compile(r'<h2>(.*?)(?:&nbsp;)?\s*<span class="helpLink"', re.S)


class CoverbrowserBlocked(Exception):
    """Raised on a 403/429 - the caller should stop the whole run, not retry."""


@dataclass
class IndexEntry:
    slug: str
    title_raw: str
    cover_count_hint: int | None


@dataclass
class SeriesPageIssue:
    number: str
    image_path: str


@dataclass
class SeriesPage:
    title_raw: str
    issues: list[SeriesPageIssue]


class ThrottledClient:
    """Single-threaded, deliberately slow HTTP client for coverbrowser.

    This is a background batch job, not a live API - unlike the Metron/
    ComicVine concurrency work elsewhere in this project, there is no
    parallelism here on purpose. A fixed delay is enforced before every
    request, and a 403/429 stops the whole run rather than retrying:
    coverbrowser has no published API or rate-limit policy and already
    started returning 429s after a handful of manual requests made while
    designing this, so backing off hard beats finding its real limit the
    hard way.
    """

    def __init__(self, user_agent: str, delay_seconds: float):
        self._client = httpx.Client(base_url=BASE_URL, headers={"User-Agent": user_agent}, timeout=15.0)
        self._delay = delay_seconds
        self._last_request_at: float | None = None

    def get(self, path: str) -> str:
        self._wait_for_slot()
        try:
            resp = self._client.get(path)
        finally:
            self._last_request_at = time.monotonic()
        if resp.status_code in (403, 429):
            raise CoverbrowserBlocked(f"{resp.status_code} from coverbrowser at {path}")
        resp.raise_for_status()
        return resp.text

    def _wait_for_slot(self) -> None:
        if self._last_request_at is None:
            return
        elapsed = time.monotonic() - self._last_request_at
        remaining = self._delay - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ThrottledClient:
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def parse_az_index_page(html: str) -> list[IndexEntry]:
    """Parses one /a-z/<bucket> page. No publisher or year is exposed here -
    just slug, display title, and a rough cover count (covers, not strictly
    issues - variants/reprints inflate it, see SeriesIndex.cover_count_hint)."""
    entries = []
    for slug, title_raw, count in _INDEX_ENTRY_RE.findall(html):
        entries.append(
            IndexEntry(
                slug=slug,
                title_raw=html_module.unescape(title_raw).strip(),
                cover_count_hint=int(count) if count else None,
            )
        )
    return entries


def parse_series_page(html: str) -> SeriesPage:
    """Parses page 1 of a /covers/<slug> series page: title plus the issue
    numbers and image paths visible on that one page. Does not follow
    pagination (a long-running series spans multiple /covers/<slug>/<n>
    pages) - that full walk belongs to the future image-download phase, not
    the matching/verification step this is used for today."""
    title_match = _SERIES_TITLE_RE.search(html)
    title_raw = html_module.unescape(title_match.group(1)).strip() if title_match else ""
    issues = [SeriesPageIssue(number=num, image_path=path) for num, path in _COVER_ENTRY_RE.findall(html)]
    return SeriesPage(title_raw=title_raw, issues=issues)


def fetch_index_bucket(client: ThrottledClient, bucket: str) -> list[IndexEntry]:
    html = client.get(f"/a-z/{bucket}")
    return parse_az_index_page(html)


def verify_first_issue_present(client: ThrottledClient, slug: str, expected_number: str = "1") -> bool:
    """Fetches page 1 of `slug` and confirms `expected_number` (GCD's own
    earliest issue number for the matched series) actually appears there.
    The one live cross-check available before permanently linking a series -
    coverbrowser exposes no publisher or cover date to verify against
    otherwise (see matcher.py's module docstring)."""
    html = client.get(f"/covers/{slug}")
    page = parse_series_page(html)
    return any(issue.number == expected_number for issue in page.issues)
