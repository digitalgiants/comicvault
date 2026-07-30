from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from comic_scraper.cache import LookupCache
from comic_scraper.config import get_settings
from comic_scraper.lookup import LookupResult, UpcLookupService
from comic_scraper.metron.client import MetronClient
from comic_scraper.metron.exceptions import MetronNotFoundError

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"
MAX_BATCH_SIZE = 20

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", force=True
)

state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    client = MetronClient(
        settings.metron_username,
        settings.metron_password,
        settings.metron_base_url,
        settings.metron_max_calls_per_minute,
    )
    cache = LookupCache(settings.database_url)
    state["service"] = UpcLookupService(client, cache)
    state["client"] = client
    yield
    client.close()


app = FastAPI(title="comic-scraper", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/lookup/{upc12}")
def lookup(upc12: str, ean5: str | None = None) -> LookupResult:
    result = state["service"].lookup(upc12, ean5)
    if result is None:
        raise HTTPException(status_code=404, detail="No issue found for that UPC")
    return result


class SeriesSearchResult(BaseModel):
    id: int
    name: str
    publisher_name: str | None = None
    year_began: int | None = None
    volume: int | None = None
    issue_count: int | None = None
    image: str | None = None


class IssueSummary(BaseModel):
    id: int
    number: str | None = None
    cover_date: str | None = None
    image: str | None = None


class IssueFields(BaseModel):
    publisher: str | None = None
    series: str
    volume: str | None = None
    issue_number: str | None = None
    cover_date: str | None = None
    store_date: str | None = None
    variant: str | None = None
    writer: str | None = None
    artist: str | None = None
    penciller: str | None = None
    inker: str | None = None
    cover_artist: str | None = None
    upc: str | None = None
    img: str | None = None


@app.get("/series/search")
def search_series(name: str) -> list[SeriesSearchResult]:
    results = state["client"].search_series(name)
    return [
        SeriesSearchResult(
            id=item["id"],
            name=item.get("name") or item.get("series", ""),
            publisher_name=(item.get("publisher") or {}).get("name") if isinstance(item.get("publisher"), dict) else item.get("publisher_name"),
            year_began=item.get("year_began"),
            volume=item.get("volume"),
            issue_count=item.get("issue_count"),
            image=item.get("image"),
        )
        for item in results
    ]


@app.get("/series/{series_id}")
def series_detail(series_id: int) -> SeriesSearchResult:
    try:
        item = state["client"].get_series(series_id)
    except MetronNotFoundError:
        raise HTTPException(status_code=404, detail="No Metron series found for that id")
    return SeriesSearchResult(
        id=item["id"],
        name=item.get("name") or item.get("series", ""),
        publisher_name=(item.get("publisher") or {}).get("name") if isinstance(item.get("publisher"), dict) else item.get("publisher_name"),
        year_began=item.get("year_began"),
        volume=item.get("volume"),
        issue_count=item.get("issue_count"),
        image=item.get("image"),
    )


@app.get("/series/{series_id}/issues")
def series_issues(series_id: int, number: str | None = None) -> list[IssueSummary]:
    results = state["client"].list_issues_by_series(series_id, number=number)
    return [
        IssueSummary(
            id=item["id"],
            number=item.get("number"),
            cover_date=item.get("cover_date"),
            image=item.get("image"),
        )
        for item in results
    ]


@app.get("/issue/{issue_id}/fields")
def issue_fields(issue_id: int) -> IssueFields:
    try:
        issue = state["client"].get_issue(issue_id)
    except MetronNotFoundError:
        raise HTTPException(status_code=404, detail="No Metron issue found for that id")

    def joined(names: list[str]) -> str | None:
        return ", ".join(names) if names else None

    return IssueFields(
        publisher=issue.publisher.name if issue.publisher else None,
        series=issue.series.name,
        volume=str(issue.series.volume) if issue.series.volume is not None else None,
        issue_number=issue.number,
        cover_date=str(issue.cover_date) if issue.cover_date else None,
        store_date=str(issue.store_date) if issue.store_date else None,
        variant=issue.variants[0].name if issue.variants else None,
        writer=joined(issue.writers),
        artist=None,
        penciller=joined(issue.pencillers),
        inker=joined(issue.inkers),
        cover_artist=joined(issue.cover_artists),
        upc=issue.upc or None,
        img=issue.image,
    )


class BatchLookupItem(BaseModel):
    upc12: str
    ean5: str | None = None


class BatchLookupRequest(BaseModel):
    items: list[BatchLookupItem]


def _batch_event_stream(items: list[BatchLookupItem]) -> Iterator[str]:
    for index, item in enumerate(items):
        event: dict = {"index": index, "upc12": item.upc12, "ean5": item.ean5}
        try:
            result = state["service"].lookup(item.upc12, item.ean5)
        except Exception as exc:  # noqa: BLE001 - one bad item shouldn't kill the whole stream
            event["status"] = "error"
            event["message"] = str(exc)
        else:
            if result is None:
                event["status"] = "not_found"
            else:
                event["status"] = "success"
                event["result"] = result.model_dump()
        yield f"data: {json.dumps(event)}\n\n"


@app.post("/lookup/batch")
def lookup_batch(payload: BatchLookupRequest) -> StreamingResponse:
    if len(payload.items) > MAX_BATCH_SIZE:
        raise HTTPException(status_code=400, detail=f"Batch limited to {MAX_BATCH_SIZE} items")
    return StreamingResponse(_batch_event_stream(payload.items), media_type="text/event-stream")


# Populated by the Docker build (frontend/dist copied to /app/static). Mounted last so it
# only catches requests that don't match /health or /lookup above; absent in plain local dev.
if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
