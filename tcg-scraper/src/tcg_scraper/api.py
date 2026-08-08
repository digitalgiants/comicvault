from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from tcg_scraper.apitcg.client import ApiTcgClient
from tcg_scraper.apitcg.exceptions import ApiTcgAuthError, ApiTcgError, ApiTcgNotFoundError
from tcg_scraper.cache import cached
from tcg_scraper.config import get_settings
from tcg_scraper.ollama.client import OllamaClient
from tcg_scraper.ollama.exceptions import (
    OllamaError,
    OllamaModelNotFoundError,
    OllamaResponseParseError,
    OllamaTimeoutError,
    OllamaUnreachableError,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", force=True
)

state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    state["apitcg"] = ApiTcgClient(
        settings.apitcg_api_key,
        settings.apitcg_base_url,
        settings.apitcg_auth_header,
        settings.apitcg_max_calls_per_minute,
    )
    state["ollama"] = OllamaClient(
        settings.ollama_base_url,
        settings.ollama_vision_model,
        settings.ollama_timeout_seconds,
        settings.ollama_max_image_dimension,
    )
    yield
    state["apitcg"].close()
    state["ollama"].close()


app = FastAPI(title="tcg-scraper", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# --- Catalog proxy (normalized apitcg.com data, vault/backend persists it) ---

class NormalizedGame(BaseModel):
    external_id: str
    name: str
    logo_image_url: str | None = None


class NormalizedSet(BaseModel):
    external_id: str
    name: str
    series_external_id: str | None = None
    series_name: str | None = None
    set_code: str | None = None
    release_date: str | None = None
    printed_total: int | None = None
    total_cards: int | None = None


class NormalizedCardImages(BaseModel):
    small: str | None = None
    medium: str | None = None
    large: str | None = None


class NormalizedCard(BaseModel):
    external_id: str
    name: str
    card_number: str | None = None
    code: str | None = None
    rarity: str | None = None
    description: str | None = None
    images: NormalizedCardImages = NormalizedCardImages()
    attributes: dict = {}
    release_date: str | None = None
    average_price: float | None = None


class ProductPage(BaseModel):
    items: list[NormalizedCard]
    page: int
    has_more: bool


def _handle_apitcg_errors(exc: Exception) -> None:
    if isinstance(exc, ApiTcgAuthError):
        raise HTTPException(status_code=502, detail=str(exc))
    if isinstance(exc, ApiTcgNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ApiTcgError):
        raise HTTPException(status_code=502, detail=str(exc))
    raise exc


@app.get("/games", response_model=list[NormalizedGame])
def list_games() -> list[NormalizedGame]:
    try:
        games = cached("apitcg:games", lambda: state["apitcg"].list_games())
    except ApiTcgError as exc:
        _handle_apitcg_errors(exc)
    return [
        NormalizedGame(external_id=g.get("id", ""), name=g.get("name", ""), logo_image_url=g.get("logo"))
        for g in games
    ]


@app.get("/games/{slug}/sets", response_model=list[NormalizedSet])
def list_sets(slug: str) -> list[NormalizedSet]:
    try:
        sets = cached(f"apitcg:sets:{slug}", lambda: state["apitcg"].list_sets(slug))
    except ApiTcgError as exc:
        _handle_apitcg_errors(exc)
    return [
        NormalizedSet(
            external_id=s.get("id", ""),
            name=s.get("name", ""),
            series_external_id=s.get("series"),
            set_code=s.get("code"),
            release_date=s.get("releaseDate"),
            printed_total=s.get("printedTotal"),
            total_cards=s.get("total"),
        )
        for s in sets
    ]


def _normalize_product(item: dict) -> NormalizedCard:
    images = item.get("images") or {}
    markets = item.get("markets") or {}
    # apitcg's markets shape is unverified beyond "contains tcgplayer/tcgmatch
    # pricing" - take the first numeric price found anywhere in it as a rough
    # average_price rather than assuming a specific nested key layout.
    average_price = None
    for source in markets.values():
        if isinstance(source, dict):
            for v in source.values():
                if isinstance(v, (int, float)):
                    average_price = float(v)
                    break
        if average_price is not None:
            break
    return NormalizedCard(
        external_id=str(item.get("_id", "")),
        name=item.get("name", ""),
        card_number=item.get("cardNumber"),
        code=item.get("code"),
        rarity=(item.get("attributes") or {}).get("Rarity"),
        description=item.get("description"),
        images=NormalizedCardImages(
            small=images.get("small"), medium=images.get("medium"), large=images.get("large"),
        ),
        attributes=item.get("attributes") or {},
        release_date=item.get("release_date"),
        average_price=average_price,
    )


@app.get("/games/{slug}/sets/{set_external_id}/products", response_model=ProductPage)
def list_products(slug: str, set_external_id: str, page: int = 1, limit: int = 250) -> ProductPage:
    try:
        data = state["apitcg"].search_products(slug, "card", set_external_id, page, limit)
    except ApiTcgError as exc:
        _handle_apitcg_errors(exc)
    items = data.get("data", data) if isinstance(data, dict) else data
    # Pagination envelope shape is unverified - has_more defaults to False
    # (i.e. "assume one page") unless apitcg tells us otherwise via a
    # recognizable total/page-count field.
    total = data.get("total") if isinstance(data, dict) else None
    has_more = bool(total) and page * limit < total
    return ProductPage(items=[_normalize_product(i) for i in items], page=page, has_more=has_more)


@app.get("/products/{external_id}", response_model=NormalizedCard)
def get_product(external_id: str) -> NormalizedCard:
    try:
        item = state["apitcg"].get_product(external_id)
    except ApiTcgError as exc:
        _handle_apitcg_errors(exc)
    return _normalize_product(item)


@app.get("/products/{external_id}/price-history")
def get_price_history(external_id: str) -> list[dict]:
    try:
        return state["apitcg"].get_price_history(external_id)
    except ApiTcgError as exc:
        _handle_apitcg_errors(exc)


# --- Identification ---

class IdentifyResponse(BaseModel):
    detected_name: str | None = None
    detected_number: str | None = None
    detected_set: str | None = None
    detected_language: str | None = None
    detected_variant: str | None = None
    detected_game_slug: str | None = None
    model_confidence: float | None = None
    raw_response: dict


@app.post("/identify", response_model=IdentifyResponse)
async def identify(file: UploadFile = File(...)) -> IdentifyResponse:
    image_bytes = await file.read()
    try:
        result = state["ollama"].identify_card(image_bytes)
    except OllamaUnreachableError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except OllamaTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc))
    except OllamaModelNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except OllamaResponseParseError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except OllamaError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return IdentifyResponse(
        detected_name=result.get("name"),
        detected_number=result.get("number"),
        detected_set=result.get("set"),
        detected_language=result.get("language"),
        detected_variant=result.get("variant"),
        detected_game_slug=result.get("game"),
        model_confidence=result.get("confidence"),
        raw_response=result.get("_raw", {}),
    )
