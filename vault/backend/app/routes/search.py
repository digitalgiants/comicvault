import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_non_kiosk
from app.config import settings
from app.external import comicvine
from app.external.comicvine import ComicVineNotConfigured, ComicVineRateLimitError
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
    current_user: User = Depends(get_current_non_kiosk),
) -> ExternalSeriesSearchResult:
    results: list[ExternalSeriesResult] = []
    warnings: list[str] = []

    try:
        resp = httpx.get(
            f"{settings.comic_scraper_url}/series/search",
            params={"name": query},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        results.extend(
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
        )
    except httpx.RequestError:
        warnings.append("Metron is unavailable")
    except Exception:
        warnings.append("Metron search failed")

    try:
        results.extend(comicvine.search_series(query))
    except ComicVineNotConfigured:
        warnings.append("ComicVine is not configured")
    except ComicVineRateLimitError:
        warnings.append("ComicVine rate limit reached, showing other results only")
    except Exception:
        warnings.append("ComicVine search failed")

    results.sort(key=lambda r: r.name)
    return ExternalSeriesSearchResult(results=results, warnings=warnings)


@router.get("/series/{provider}/{provider_series_id}/issues", response_model=list[ExternalIssueSummary])
def get_series_issues(
    provider: str,
    provider_series_id: str,
    current_user: User = Depends(get_current_non_kiosk),
) -> list[ExternalIssueSummary]:
    if provider == "metron":
        try:
            resp = httpx.get(
                f"{settings.comic_scraper_url}/series/{provider_series_id}/issues",
                timeout=TIMEOUT,
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
            return comicvine.get_series_issues(provider_series_id)
        except ComicVineNotConfigured as e:
            raise HTTPException(status_code=400, detail=str(e))
        except ComicVineRateLimitError as e:
            raise HTTPException(status_code=429, detail=str(e))
    raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")


@router.get("/issue/{provider}/{provider_issue_id}", response_model=ComicCreate)
def get_issue_fields(
    provider: str,
    provider_issue_id: str,
    current_user: User = Depends(get_current_non_kiosk),
) -> ComicCreate:
    if provider == "metron":
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
        return ComicCreate(**resp.json())
    elif provider == "comicvine":
        try:
            return comicvine.get_issue_fields(provider_issue_id)
        except ComicVineNotConfigured as e:
            raise HTTPException(status_code=400, detail=str(e))
        except ComicVineRateLimitError as e:
            raise HTTPException(status_code=429, detail=str(e))
    raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
