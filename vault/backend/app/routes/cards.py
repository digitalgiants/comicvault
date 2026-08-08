import uuid
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, File
from sqlalchemy.orm import Session

from app import crud_cards
from app.auth import get_current_non_kiosk
from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import (
    CardBulkUpdateRequest, CardGameOut, CardSaleCreate, CardSaleUpdate, CardScanConfirmRequest,
    CardTransactionOut, IdentifyScanResponse, ScanCandidateOut, TradingCardOut,
    UserTradingCardCreate, UserTradingCardOut, UserTradingCardUpdate,
)

router = APIRouter(prefix="/cards", tags=["cards"])

PHOTO_DIR = Path("/app/uploads/card_personal_img")
PHOTO_DIR.mkdir(parents=True, exist_ok=True)
# Same limits as routes/comics.py's PHOTO_DIR - kept identical rather than
# invented anew, no reason ownership photos of cards differ from comics.
MAX_PHOTO_SIZE = 3 * 1024 * 1024  # 3MB
MIN_PHOTO_SIZE = 2 * 1024  # 2KB
ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}

SCAN_DIR = Path("/app/uploads/card_scans")
SCAN_DIR.mkdir(parents=True, exist_ok=True)
# Bigger than MAX_PHOTO_SIZE above - a full, uncropped smartphone photo for
# AI extraction is legitimately larger than a cropped personal-copy photo.
MAX_SCAN_PHOTO_SIZE = 8 * 1024 * 1024  # 8MB
MIN_SCAN_PHOTO_SIZE = 2 * 1024
# tcg-scraper -> Ollama; CPU-only inference is slow. Not the comics scan
# flow's 15s LOOKUP_TIMEOUT - this is a genuinely different latency profile.
IDENTIFY_TIMEOUT = 100.0


@router.get("/", response_model=list[TradingCardOut])
def search_cards(
    name: str | None = Query(None),
    game_slug: str | None = Query(None),
    set_id: int | None = Query(None),
    card_number: str | None = Query(None),
    rarity: str | None = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_non_kiosk),
):
    return crud_cards.search_trading_cards(
        db, name=name, game_slug=game_slug, set_id=set_id,
        card_number=card_number, rarity=rarity, skip=skip, limit=limit,
    )


@router.get("/games", response_model=list[CardGameOut])
def list_games(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_non_kiosk),
):
    return crud_cards.list_games(db)


@router.get("/collection", response_model=list[UserTradingCardOut])
def get_my_card_collection(
    response: Response,
    name: str | None = Query(None),
    game_slug: str | None = Query(None),
    skip: int = 0,
    limit: int = 200,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    items, total = crud_cards.get_user_card_collection(
        db, current_user.id, name=name, game_slug=game_slug, skip=skip, limit=limit,
    )
    response.headers["X-Total-Count"] = str(total)
    return items


@router.post("/collection", response_model=UserTradingCardOut, status_code=201)
def add_to_card_collection(
    uc_in: UserTradingCardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    if crud_cards.get_card_by_id(db, uc_in.card_id) is None:
        raise HTTPException(status_code=404, detail="Card not found")
    return crud_cards.create_user_trading_card(db, current_user.id, uc_in)


@router.put("/collection/{uc_id}", response_model=UserTradingCardOut)
def update_user_trading_card(
    uc_id: int,
    update: UserTradingCardUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    uc = crud_cards.update_user_trading_card(db, current_user.id, uc_id, update)
    if not uc:
        raise HTTPException(status_code=404, detail="Not found")
    return uc


@router.post("/collection/bulk", response_model=dict)
def bulk_update(
    req: CardBulkUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    updates = [{"id": item.id, "update": item.update.model_dump(exclude_unset=True)} for item in req.updates]
    count = crud_cards.bulk_update_user_trading_cards(db, current_user.id, updates)
    return {"updated": count}


@router.delete("/collection/{uc_id}", status_code=204)
def remove_from_card_collection(
    uc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    if not crud_cards.delete_user_trading_card(db, current_user.id, uc_id):
        raise HTTPException(status_code=404, detail="Not found")


@router.post("/collection/{uc_id}/photo", response_model=UserTradingCardOut)
async def upload_card_photo(
    uc_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    if not crud_cards.get_user_trading_card_by_id(db, current_user.id, uc_id):
        raise HTTPException(status_code=404, detail="Not found")
    if file.content_type not in ALLOWED_PHOTO_TYPES:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, or WEBP images are accepted")

    contents = await file.read()
    if len(contents) > MAX_PHOTO_SIZE:
        raise HTTPException(status_code=400, detail="Image too large (max 3MB)")
    if len(contents) < MIN_PHOTO_SIZE:
        raise HTTPException(status_code=400, detail="That photo looks blank or corrupted - please retake it")

    filename = f"{uuid.uuid4()}.jpg"
    (PHOTO_DIR / filename).write_bytes(contents)

    uc = crud_cards.set_user_trading_card_photo(db, current_user.id, uc_id, f"/uploads/card_personal_img/{filename}")
    return uc


@router.post("/collection/{uc_id}/sales", response_model=CardTransactionOut, status_code=201)
def record_card_sale(
    uc_id: int,
    sale_in: CardSaleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    sale = crud_cards.create_card_sale(db, current_user.id, uc_id, sale_in)
    if sale is None:
        uc = crud_cards.get_user_trading_card_by_id(db, current_user.id, uc_id)
        if not uc:
            raise HTTPException(status_code=404, detail="Not found")
        raise HTTPException(status_code=400, detail="All copies of this card have already been sold.")
    return sale


@router.put("/collection/{uc_id}/sales/{txn_id}", response_model=CardTransactionOut)
def update_card_sale(
    uc_id: int,
    txn_id: int,
    update: CardSaleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    sale = crud_cards.update_card_sale(db, current_user.id, uc_id, txn_id, update)
    if not sale:
        raise HTTPException(status_code=404, detail="Sale record not found")
    return sale


@router.delete("/collection/{uc_id}/sales/{txn_id}", status_code=204)
def delete_card_sale(
    uc_id: int,
    txn_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    if not crud_cards.delete_card_sale(db, current_user.id, uc_id, txn_id):
        raise HTTPException(status_code=404, detail="Sale record not found")


# --- Scan / identification pipeline ---
# Photo -> tcg-scraper (Ollama vision model) -> structured extraction ->
# candidate match against the local catalog -> user confirmation -> collection
# record. Never auto-confirms - always returns candidates for the user to
# pick from, even a single high-confidence one (design rule carried over
# from feature-requests/tcg_card_scanner_build_prompt.md: never destroy
# uncertainty, never silently add a questionable identification).

@router.post("/scan/identify", response_model=IdentifyScanResponse)
async def identify_card(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    if file.content_type not in ALLOWED_PHOTO_TYPES:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, or WEBP images are accepted")

    contents = await file.read()
    if len(contents) > MAX_SCAN_PHOTO_SIZE:
        raise HTTPException(status_code=400, detail="Image too large (max 8MB)")
    if len(contents) < MIN_SCAN_PHOTO_SIZE:
        raise HTTPException(status_code=400, detail="That photo looks blank or corrupted - please retake it")

    filename = f"{uuid.uuid4()}.jpg"
    (SCAN_DIR / filename).write_bytes(contents)
    image_url = f"/uploads/card_scans/{filename}"

    try:
        resp = httpx.post(
            f"{settings.tcg_scraper_url}/identify",
            files={"file": (filename, contents, file.content_type)},
            timeout=IDENTIFY_TIMEOUT,
        )
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="Card identification service unavailable")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Identification timed out - the model may still be warming up, try again shortly")

    if resp.status_code == 503:
        raise HTTPException(status_code=503, detail=resp.json().get("detail", "Identification model isn't ready yet"))
    if resp.is_error:
        raise HTTPException(status_code=502, detail="Card identification service returned an error")

    detected = resp.json()
    game_slug = detected.get("detected_game_slug")
    detected_game = crud_cards.get_game_by_slug(db, game_slug) if game_slug else None

    candidates = crud_cards.match_candidates(
        db,
        detected_name=detected.get("detected_name"),
        detected_number=detected.get("detected_number"),
        detected_set=detected.get("detected_set"),
        detected_game_slug=game_slug,
    )

    scan = crud_cards.create_identification_scan(
        db, current_user.id, image_url,
        detected={
            "detected_name": detected.get("detected_name"),
            "detected_number": detected.get("detected_number"),
            "detected_set": detected.get("detected_set"),
            "detected_language": detected.get("detected_language"),
            "detected_variant": detected.get("detected_variant"),
            "detected_game_id": detected_game.id if detected_game else None,
        },
        raw_response=detected.get("raw_response") or {},
    )
    crud_cards.add_identification_matches(
        db, scan.id,
        [(card.id, variant_id, confidence, method) for card, variant_id, confidence, method in candidates],
    )

    return IdentifyScanResponse(
        scan_id=scan.id,
        image_url=image_url,
        detected_name=detected.get("detected_name"),
        detected_number=detected.get("detected_number"),
        detected_set=detected.get("detected_set"),
        detected_language=detected.get("detected_language"),
        detected_variant=detected.get("detected_variant"),
        candidates=[
            ScanCandidateOut(card=card, variant_id=variant_id, confidence=confidence, match_method=method)
            for card, variant_id, confidence, method in candidates
        ],
    )


@router.post("/scan/{scan_id}/confirm", response_model=UserTradingCardOut)
def confirm_card_scan(
    scan_id: int,
    payload: CardScanConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    scan = crud_cards.get_identification_scan(db, current_user.id, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if crud_cards.get_card_by_id(db, payload.candidate_card_id) is None:
        raise HTTPException(status_code=404, detail="Card not found")

    ownership_fields = payload.user_trading_card.model_dump(exclude_unset=True)
    # Default personal_img to the scan's own photo - the user already took a
    # usable photo to get here, no need to ask them to photograph it twice.
    ownership_fields.setdefault("personal_img", scan.image_url)
    ownership = UserTradingCardCreate(
        card_id=payload.candidate_card_id,
        variant_id=payload.variant_id,
        **ownership_fields,
    )

    return crud_cards.create_user_trading_card(db, current_user.id, ownership)
