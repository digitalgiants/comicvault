import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import crud, gcd_lookup
from app.auth import get_current_non_kiosk
from app.config import settings
from app.database import get_db
from app.external import comicvine
from app.external.comicvine import ComicVineNotConfigured, ComicVineRateLimitError
from app.gcd_database import get_gcd_db
from app.models import User
from app.schemas import (
    ComicCreate,
    ExternalIssueSummary,
    ExternalSeriesResult,
    ExternalSeriesSearchResult,
)

router = APIRouter(prefix="/search", tags=["search"])

TIMEOUT = 15.0


@router.get("/series", response_model=ExternalSeriesSearchResult)
def search_series(
    query: str,
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    gcd_db: Session | None = Depends(get_gcd_db),
    current_user: User = Depends(get_current_non_kiosk),
) -> ExternalSeriesSearchResult:
    # GCD is free/local (no API cost) so it's tried first; Metron/ComicVine
    # (both cost real API calls) only get hit when GCD has nothing at all on
    # the first page. A later page (offset > 0) means GCD already won on
    # page 1, so it keeps paginating GCD rather than switching providers
    # mid-scroll - an empty later page just means "no more GCD results".
    if gcd_db is not None:
        gcd_results, gcd_total = gcd_lookup.search_series(gcd_db, query, offset=offset)
        if gcd_results or offset > 0:
            has_more = offset + len(gcd_results) < gcd_total
            return ExternalSeriesSearchResult(results=gcd_results, warnings=[], has_more=has_more)

    normalized = crud.normalize_search_query(query)
    results: list[ExternalSeriesResult] = []
    warnings: list[str] = []

    metron_cached = crud.get_cached_series_search(db, "metron", normalized)
    if metron_cached is not None:
        results.extend(metron_cached)
    else:
        try:
            resp = httpx.get(
                f"{settings.comic_scraper_url}/series/search",
                params={"name": query},
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            metron_results = [
                ExternalSeriesResult(
                    provider="metron",
                    provider_series_id=str(item["id"]),
                    name=item["name"],
                    publisher=item.get("publisher_name"),
                    start_year=item.get("year_began"),
                    issue_count=item.get("issue_count"),
                    image=item.get("image"),
                )
                for item in resp.json()
            ]
            results.extend(metron_results)
            crud.save_series_search_cache(db, "metron", normalized, metron_results)
        except Exception:
            stale = crud.get_cached_series_search(db, "metron", normalized, ignore_ttl=True)
            if stale:
                results.extend(stale)
                warnings.append("Metron is unavailable - showing cached results")
            else:
                warnings.append("Metron is unavailable")

    comicvine_cached = crud.get_cached_series_search(db, "comicvine", normalized)
    if comicvine_cached is not None:
        results.extend(comicvine_cached)
    else:
        try:
            comicvine_results = comicvine.search_series(query)
            results.extend(comicvine_results)
            crud.save_series_search_cache(db, "comicvine", normalized, comicvine_results)
        except ComicVineNotConfigured:
            warnings.append("ComicVine is not configured")
        except ComicVineRateLimitError:
            stale = crud.get_cached_series_search(db, "comicvine", normalized, ignore_ttl=True)
            if stale:
                results.extend(stale)
                warnings.append("ComicVine rate limit reached - showing cached results")
            else:
                warnings.append("ComicVine rate limit reached, showing other results only")
        except Exception:
            stale = crud.get_cached_series_search(db, "comicvine", normalized, ignore_ttl=True)
            if stale:
                results.extend(stale)
                warnings.append("ComicVine search failed - showing cached results")
            else:
                warnings.append("ComicVine search failed")

    results.sort(key=lambda r: r.name)
    return ExternalSeriesSearchResult(results=results, warnings=warnings)


def _fetch_provider_issues(
    provider: str, provider_series_id: str, number: str | None = None, gcd_db: Session | None = None
) -> list[ExternalIssueSummary]:
    """Fetch issues directly from the provider (bypassing our cache) - either
    the full series (number=None) or, if number is given, a single targeted
    issue via the provider's own filter so we don't have to page through a
    whole long-running series just to find one."""
    if provider == "metron":
        try:
            resp = httpx.get(
                f"{settings.comic_scraper_url}/series/{provider_series_id}/issues",
                params={"number": number} if number else None,
                timeout=TIMEOUT * 4,  # a full series can take several paginated round trips
            )
            resp.raise_for_status()
        except httpx.RequestError:
            raise HTTPException(status_code=502, detail="Metron lookup service unavailable")
        return [
            ExternalIssueSummary(
                provider="metron",
                provider_issue_id=str(item["id"]),
                number=item.get("number"),
                cover_date=item.get("cover_date"),
                image=item.get("image"),
            )
            for item in resp.json()
        ]
    elif provider == "comicvine":
        try:
            return comicvine.get_series_issues(provider_series_id, number=number)
        except ComicVineNotConfigured as e:
            raise HTTPException(status_code=400, detail=str(e))
        except ComicVineRateLimitError as e:
            raise HTTPException(status_code=429, detail=str(e))
    elif provider == "gcd":
        if gcd_db is None:
            raise HTTPException(status_code=400, detail="GCD lookup is not configured")
        return gcd_lookup.get_series_issues(gcd_db, int(provider_series_id), number=number)
    raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")


def _current_issue_count(provider: str, provider_series_id: str) -> int | None:
    """Cheap freshness check: how many issues does the provider report for
    this series right now. Used to decide whether a cached series needs a
    re-sync, without paying the cost of re-paginating on every visit."""
    try:
        if provider == "metron":
            resp = httpx.get(
                f"{settings.comic_scraper_url}/series/{provider_series_id}",
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json().get("issue_count")
        elif provider == "comicvine":
            return comicvine.get_series_issue_count(provider_series_id)
    except Exception:
        return None
    return None


@router.get("/series/{provider}/{provider_series_id}/issues", response_model=list[ExternalIssueSummary])
def get_series_issues(
    provider: str,
    provider_series_id: str,
    number: str | None = Query(None),
    series_name: str | None = Query(None),
    db: Session = Depends(get_db),
    gcd_db: Session | None = Depends(get_gcd_db),
    current_user: User = Depends(get_current_non_kiosk),
) -> list[ExternalIssueSummary]:
    if provider not in ("metron", "comicvine", "gcd"):
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    # Targeted "series + issue number" lookup: serve from cache if we've seen
    # it, otherwise ask the provider for just that one issue. We pass `number`
    # to the provider so it can filter server-side when it can, but we never
    # trust that it actually did - the provider's filter param names haven't
    # been verified against a live call, so we always confirm the match
    # ourselves rather than assuming a small/empty result means it worked.
    if number:
        hit = crud.find_cached_issue_by_number(db, provider, provider_series_id, number)
        if hit:
            return [hit]

        fetched = _fetch_provider_issues(provider, provider_series_id, number=number, gcd_db=gcd_db)
        crud.bulk_upsert_issue_summaries(db, provider, provider_series_id, fetched)

        target = crud.normalize_issue_number(number)
        matches = [i for i in fetched if crud.normalize_issue_number(i.number) == target]
        matches.sort(key=lambda i: crud.issue_number_sort_key(i.number))
        return matches

    sync = crud.get_series_sync(db, provider, provider_series_id)
    if sync is not None:
        cached_issues = crud.get_cached_issues(db, provider, provider_series_id)
        if cached_issues:
            current_count = _current_issue_count(provider, provider_series_id)
            # If the check fails or the count matches, the cache is still good.
            # Only a higher count (new issues published since our last sync)
            # is worth paying to re-fetch for.
            if current_count is None or current_count <= sync.known_issue_count:
                return cached_issues

    fetched = _fetch_provider_issues(provider, provider_series_id, gcd_db=gcd_db)
    fetched.sort(key=lambda i: crud.issue_number_sort_key(i.number))
    crud.bulk_upsert_issue_summaries(db, provider, provider_series_id, fetched)
    crud.upsert_series_sync(db, provider, provider_series_id, series_name, len(fetched))
    return fetched


@router.get("/issue/{provider}/{provider_issue_id}", response_model=ComicCreate)
def get_issue_fields(
    provider: str,
    provider_issue_id: str,
    db: Session = Depends(get_db),
    gcd_db: Session | None = Depends(get_gcd_db),
    current_user: User = Depends(get_current_non_kiosk),
) -> ComicCreate:
    cached_row = crud.get_cached_issue_fields(db, provider, provider_issue_id)
    if cached_row is not None and cached_row.fields_synced:
        return crud.cache_row_to_comic_create(cached_row)

    if provider == "gcd":
        if gcd_db is None:
            raise HTTPException(status_code=400, detail="GCD lookup is not configured")
        try:
            fields = gcd_lookup.get_issue_fields(gcd_db, int(provider_issue_id))
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
    elif provider == "metron":
        try:
            resp = httpx.get(
                f"{settings.comic_scraper_url}/issue/{provider_issue_id}/fields",
                timeout=TIMEOUT,
            )
        except httpx.RequestError:
            raise HTTPException(status_code=502, detail="Metron lookup service unavailable")
        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail="No Metron issue found for that id")
        resp.raise_for_status()
        fields = ComicCreate(**resp.json())
    elif provider == "comicvine":
        try:
            fields = comicvine.get_issue_fields(provider_issue_id)
        except ComicVineNotConfigured as e:
            raise HTTPException(status_code=400, detail=str(e))
        except ComicVineRateLimitError as e:
            raise HTTPException(status_code=429, detail=str(e))
    else:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    crud.update_issue_cache_fields(db, provider, provider_issue_id, fields)
    return fields
