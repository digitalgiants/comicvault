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
