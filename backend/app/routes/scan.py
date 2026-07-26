import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app import crud
from app.auth import get_current_non_kiosk
from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import ScanAddRequest, UserComicCreate, UserComicOut

router = APIRouter(prefix="/scan", tags=["scan"])

LOOKUP_TIMEOUT = 15.0


@router.get("/lookup/{upc12}")
def lookup_barcode(
    upc12: str,
    ean5: str | None = None,
    current_user: User = Depends(get_current_non_kiosk),
):
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
