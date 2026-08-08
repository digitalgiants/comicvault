from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from tcg_scraper.apitcg.client import MAX_PAGE_SIZE, ApiTcgClient
from tcg_scraper.apitcg.exceptions import (
    ApiTcgAuthError, ApiTcgError, ApiTcgNotFoundError, ApiTcgQuotaExceededError,
)
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
        settings.apitcg_monthly_call_limit,
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


@app.get("/apitcg/usage")
def apitcg_usage() -> dict:
    """In-process only - resets on container restart, does not track calls
    made outside this process. Check apitcg.com's own dashboard for the
    real monthly total before relying on this for anything precise."""
    client: ApiTcgClient = state["apitcg"]
    return {
        "calls_this_process": client.calls_made_this_process(),
        "limit": client.monthly_call_limit,
    }


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
    # Every product response embeds its own full set object (confirmed live -
    # see feature-requests/apitcg-calls) - carried here so a whole-catalog
    # sync can resolve/create the set on the fly without a separate
    # per-set pre-sync step.
    set_external_id: str | None = None
    set_name: str | None = None
    set_code: str | None = None


class ProductPage(BaseModel):
    items: list[NormalizedCard]
    page: int
    has_more: bool


def _handle_apitcg_errors(exc: Exception) -> None:
    if isinstance(exc, ApiTcgAuthError):
        raise HTTPException(status_code=502, detail=str(exc))
    if isinstance(exc, ApiTcgNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ApiTcgQuotaExceededError):
        raise HTTPException(status_code=429, detail=str(exc))
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
        # apitcg is Mongoose/MongoDB-backed (confirmed live via the embedded
        # tcg/set objects on a real product response, which both use "_id" -
        # __v, createdAt, updatedAt are Mongoose hallmarks too), so the
        # top-level /tcgs collection almost certainly keys on "_id" as well,
        # not "id". Getting this wrong isn't cosmetic: every game fell back
        # to the same empty-string default and silently overwrote the same
        # single DB row on every sync, leaving only whichever game was last
        # in the response. "logo" is still an unverified guess.
        NormalizedGame(external_id=g.get("_id", ""), name=g.get("name", ""), logo_image_url=g.get("logo"))
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
            # Same "_id" fix as list_games above, plus two more confirmed
            # against the embedded set object on a real product response:
            # the field is "serie" (no trailing s), and "release_date" is
            # snake_case, not "releaseDate". set_code/printed_total/
            # total_cards remain unverified guesses - the embedded
            # per-product set object doesn't show them either way.
            external_id=s.get("_id", ""),
            name=s.get("name", ""),
            series_external_id=s.get("serie"),
            set_code=s.get("code"),
            release_date=s.get("release_date"),
            printed_total=s.get("printedTotal"),
            total_cards=s.get("total"),
        )
        for s in sets
    ]


def _normalize_product(item: dict) -> NormalizedCard:
    # Confirmed live shape (feature-requests/apitcg-calls) - "images" is a
    # LIST of {small,medium,large} objects, not a single object.
    images_list = item.get("images") or []
    images = images_list[0] if images_list else {}
    attributes = item.get("attributes") or {}
    set_obj = item.get("set") or {}
    markets = item.get("markets") or {}

    # Confirmed shape: markets.<source>.prices.{low,mid,high,market} - one
    # level deeper than originally guessed. Prefer "market", fall back to
    # any other numeric price tier found.
    average_price = None
    for source in markets.values():
        if not isinstance(source, dict):
            continue
        prices = source.get("prices")
        if isinstance(prices, dict):
            if isinstance(prices.get("market"), (int, float)):
                average_price = float(prices["market"])
                break
            numeric = [v for v in prices.values() if isinstance(v, (int, float))]
            if numeric:
                average_price = float(numeric[0])
                break

    return NormalizedCard(
        external_id=str(item.get("_id", "")),
        name=item.get("name", ""),
        # No "cardNumber" field exists on the wire - "code" IS the card
        # number (e.g. "91/119"), duplicated in attributes.Number.
        card_number=item.get("code") or attributes.get("Number"),
        code=item.get("code"),
        rarity=attributes.get("Rarity"),
        description=item.get("description"),
        images=NormalizedCardImages(
            small=images.get("small"), medium=images.get("medium"), large=images.get("large"),
        ),
        attributes=attributes,
        # Cards have no release_date of their own - it lives on the
        # embedded set object.
        release_date=set_obj.get("release_date"),
        average_price=average_price,
        set_external_id=set_obj.get("_id"),
        set_name=set_obj.get("name"),
        set_code=set_obj.get("code"),
    )


@app.get("/games/{slug}/sets/{set_external_id}/products", response_model=ProductPage)
def list_products(slug: str, set_external_id: str, page: int = 1, limit: int = MAX_PAGE_SIZE) -> ProductPage:
    try:
        data = state["apitcg"].search_products(slug, "card", set_external_id, page, limit)
    except ApiTcgError as exc:
        _handle_apitcg_errors(exc)
    return _product_page_from_response(data, page, limit)


@app.get("/games/{slug}/products", response_model=ProductPage)
def list_all_products(slug: str, page: int = 1, limit: int = MAX_PAGE_SIZE) -> ProductPage:
    """Paginates the WHOLE catalog for a game in one pass, no per-set
    looping - confirmed viable live (feature-requests/apitcg-calls: a single
    ?tcg=pokemon&type=card query reports total=27812 and pages cleanly at
    limit=100). Each item embeds its own set info (see NormalizedCard), so
    the caller can upsert sets on the fly rather than requiring them synced
    first - ~280 calls for the entire Pokemon catalog, well under the
    1,000/month free-tier quota."""
    try:
        data = state["apitcg"].search_products(slug, "card", None, page, limit)
    except ApiTcgError as exc:
        _handle_apitcg_errors(exc)
    return _product_page_from_response(data, page, limit)


def _product_page_from_response(data: dict, page: int, limit: int) -> ProductPage:
    items = data.get("data", data) if isinstance(data, dict) else data
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
