import threading
import time
from collections import deque

import httpx

from app.config import settings
from app.external.cache import cached
from app.schemas import ComicCreate, ExternalIssueSummary, ExternalSeriesResult

BASE_URL = "https://comicvine.gamespot.com/api"
RATE_LIMIT_PER_HOUR = 180

# ComicVine resource ids are exposed unprefixed in list/search results but the
# detail endpoint requires the "4000-" issue-resource prefix on the path.
_ISSUE_RESOURCE_PREFIX = "4000"

_request_times: deque[float] = deque()
_rate_limit_lock = threading.Lock()


class ComicVineNotConfigured(Exception):
    pass


class ComicVineRateLimitError(Exception):
    pass


def _check_rate_limit() -> None:
    # Locked because search.py now fires several ComicVine calls concurrently
    # per request (see _find_cover_images) - unlocked check-then-append here
    # would let two threads both read a count just under the limit and both
    # proceed, silently exceeding RATE_LIMIT_PER_HOUR.
    with _rate_limit_lock:
        now = time.monotonic()
        while _request_times and now - _request_times[0] > 3600:
            _request_times.popleft()
        if len(_request_times) >= RATE_LIMIT_PER_HOUR:
            raise ComicVineRateLimitError("ComicVine hourly rate limit reached")
        _request_times.append(now)


def _get(path: str, params: dict) -> dict:
    if not settings.comicvine_api_key:
        raise ComicVineNotConfigured("ComicVine API key is not configured")
    _check_rate_limit()
    with httpx.Client(
        base_url=BASE_URL,
        headers={"User-Agent": "ComicVault/1.0"},
        timeout=10,
    ) as client:
        resp = client.get(
            path,
            params={**params, "api_key": settings.comicvine_api_key, "format": "json"},
        )
        resp.raise_for_status()
        return resp.json()


def _credits_by_role(person_credits: list[dict], role_substring: str) -> str | None:
    names = [
        c["name"]
        for c in person_credits
        if role_substring in c.get("role", "").lower()
    ]
    return ", ".join(names) if names else None


def search_series(query: str) -> list[ExternalSeriesResult]:
    def fetch() -> list[ExternalSeriesResult]:
        data = _get("/search/", {"resources": "volume", "query": query})
        return [
            ExternalSeriesResult(
                provider="comicvine",
                provider_series_id=str(item["id"]),
                name=item.get("name", ""),
                publisher=(item.get("publisher") or {}).get("name"),
                start_year=int(item["start_year"]) if item.get("start_year") else None,
                issue_count=item.get("count_of_issues"),
                image=(item.get("image") or {}).get("original_url"),
            )
            for item in data.get("results", [])
        ]

    return cached(f"comicvine:series:{query.lower()}", fetch)


def get_series_issue_count(series_id: str) -> int | None:
    """Uncached on purpose - used to check whether a cached series is stale."""
    data = _get(f"/volume/{series_id}/", {"field_list": "count_of_issues"})
    item = data.get("results") or {}
    return item.get("count_of_issues")


_PAGE_SIZE = 100


def get_series_issues(series_id: str, number: str | None = None) -> list[ExternalIssueSummary]:
    """Fetch every issue for a series, paging through ComicVine's offset-based results.

    ComicVine caps a single request at 100 results with no cursor - the
    un-paginated version of this call silently returned only the first 100,
    missing most of a long-running series. `number` narrows to a single issue
    server-side, so callers that just want one specific issue don't have to
    page through the whole run.
    """
    filter_parts = [f"volume:{series_id}"]
    if number is not None:
        filter_parts.append(f"issue_number:{number}")
    filter_value = ",".join(filter_parts)

    def fetch() -> list[ExternalIssueSummary]:
        items: list[dict] = []
        offset = 0
        while True:
            data = _get(
                "/issues/",
                {
                    "filter": filter_value,
                    "field_list": "id,issue_number,name,cover_date,image",
                    "limit": _PAGE_SIZE,
                    "offset": offset,
                },
            )
            page = data.get("results", [])
            items.extend(page)
            offset += len(page)
            total = data.get("number_of_total_results", len(items))
            if len(page) < _PAGE_SIZE or offset >= total:
                break

        return [
            ExternalIssueSummary(
                provider="comicvine",
                provider_issue_id=str(item["id"]),
                number=item.get("issue_number"),
                cover_date=item.get("cover_date"),
                image=(item.get("image") or {}).get("original_url"),
            )
            for item in items
        ]

    cache_key = f"comicvine:issues:{series_id}" if number is None else f"comicvine:issues:{series_id}:{number}"
    return cached(cache_key, fetch)


def get_issue_fields(issue_id: str) -> ComicCreate:
    resource_id = issue_id if "-" in issue_id else f"{_ISSUE_RESOURCE_PREFIX}-{issue_id}"
    data = _get(f"/issue/{resource_id}/", {})
    item = data.get("results", {})
    volume = item.get("volume") or {}
    person_credits = item.get("person_credits", [])

    return ComicCreate(
        publisher=None,
        series=volume.get("name", ""),
        volume=None,
        issue_number=item.get("issue_number"),
        cover_date=item.get("cover_date"),
        store_date=item.get("store_date"),
        variant=None,
        writer=_credits_by_role(person_credits, "writer"),
        penciller=_credits_by_role(person_credits, "penciler"),
        inker=_credits_by_role(person_credits, "inker"),
        cover_artist=_credits_by_role(person_credits, "cover"),
        average_price=None,
        upc=None,
        img=(item.get("image") or {}).get("original_url"),
    )
