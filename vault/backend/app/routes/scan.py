import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app import crud, gcd_lookup
from app.auth import get_current_non_kiosk
from app.config import settings
from app.database import get_db
from app.gcd_database import get_gcd_db
from app.models import User
from app.schemas import ScanAddRequest, UserComicCreate, UserComicOut

router = APIRouter(prefix="/scan", tags=["scan"])

LOOKUP_TIMEOUT = 15.0


@router.get("/lookup/{upc12}")
def lookup_barcode(
    upc12: str,
    ean5: str | None = None,
    gcd_db: Session | None = Depends(get_gcd_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    if gcd_db is not None:
        gcd_result = _lookup_gcd(gcd_db, upc12, ean5)
        if gcd_result is not None:
            return gcd_result

    params = {"ean5": ean5} if ean5 else {}
    try:
        resp = httpx.get(
            f"{settings.comic_scraper_url}/lookup/{upc12}",
            params=params,
            timeout=LOOKUP_TIMEOUT,
        )
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Lookup service unavailable")

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="No issue found for that UPC")
    if resp.is_error:
        raise HTTPException(status_code=502, detail="Lookup service error")
    return resp.json()


def _lookup_gcd(gcd_db: Session, upc12: str, ean5: str | None) -> dict | None:
    """GCD-first barcode match. Returns None on a miss so the caller falls
    through to the existing comic-scraper (Metron) proxy unchanged. On a hit,
    builds a response shaped exactly like comic-scraper's own LookupResult
    (see comic-scraper/src/comic_scraper/lookup.py) so the frontend needs no
    source-specific handling - it makes one extra call to comic-scraper solely
    to pull a cover image (cheap and precise, anchored by the same UPC),
    swallowing any failure since a missing image shouldn't block the add.
    """
    issue = gcd_lookup.find_issue_by_upc(gcd_db, upc12)
    if issue is None:
        return None
    fields = gcd_lookup.get_issue_fields(gcd_db, issue.id)

    image = None
    try:
        params = {"ean5": ean5} if ean5 else {}
        resp = httpx.get(
            f"{settings.comic_scraper_url}/lookup/{upc12}",
            params=params,
            timeout=LOOKUP_TIMEOUT,
        )
        if resp.is_success:
            image = resp.json().get("image")
    except httpx.RequestError:
        pass

    return {
        "series_name": fields.series,
        "issue_number": fields.issue_number or "",
        "cover_date": fields.cover_date.isoformat() if fields.cover_date else "",
        "variant_name": fields.variant,
        "cover_artists": [],
        "matched_on": "base_upc",
        "source": "gcd",
        "series_volume": int(fields.volume) if fields.volume and fields.volume.isdigit() else None,
        "publisher_name": fields.publisher,
        "store_date": fields.store_date.isoformat() if fields.store_date else None,
        "writers": [fields.writer] if fields.writer else [],
        "pencillers": [fields.penciller] if fields.penciller else [],
        "inkers": [fields.inker] if fields.inker else [],
        "credits": [],
        "metron_id": None,
        "cv_id": None,
        "gcd_id": issue.id,
        "image": image,
        "cover_hash": None,
    }


@router.post("/lookup/batch")
def lookup_barcode_batch(
    payload: dict,
    current_user: User = Depends(get_current_non_kiosk),
):
    def proxy_stream():
        try:
            with httpx.stream(
                "POST",
                f"{settings.comic_scraper_url}/lookup/batch",
                json=payload,
                timeout=None,
            ) as r:
                yield from r.iter_bytes()
        except httpx.RequestError:
            yield 'data: {"status": "error", "message": "Lookup service unavailable"}\n\n'.encode()

    return StreamingResponse(proxy_stream(), media_type="text/event-stream")


@router.post("/add", response_model=UserComicOut)
def add_scanned_comic(
    payload: ScanAddRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    comic = None
    if payload.comic.upc:
        comic = crud.get_comic_by_upc(db, payload.comic.upc)
    if comic is None:
        comic = crud.find_matching_comic(db, payload.comic.model_dump())
    if comic is None:
        comic = crud.create_comic(db, payload.comic, user_id=current_user.id)

    if crud.user_already_owns(db, current_user.id, comic.id):
        raise HTTPException(status_code=400, detail="Already in your collection")

    uc = crud.create_user_comic(
        db,
        current_user.id,
        UserComicCreate(comic_id=comic.id, **payload.user_comic.model_dump()),
    )
    crud.record_snapshot(db, current_user.id)
    return uc
