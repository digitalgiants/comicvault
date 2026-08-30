import json

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
    ean: str | None = None,
    gcd_db: Session | None = Depends(get_gcd_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    if gcd_db is not None:
        gcd_result = _lookup_gcd(gcd_db, upc12, ean)
        if gcd_result is not None:
            return gcd_result

    # comic-scraper's own API still calls this param "ean5" (its external
    # contract, a separate service/schema) - comicvault's own naming is
    # "ean" throughout, translated at this boundary rather than renaming
    # comic-scraper itself.
    params = {"ean5": ean} if ean else {}
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


def _lookup_gcd(gcd_db: Session, upc12: str, ean: str | None) -> dict | None:
    """GCD-first barcode match. Returns None on a miss so the caller falls
    through to the existing comic-scraper (Metron) proxy unchanged. On a hit,
    builds a response shaped exactly like comic-scraper's own LookupResult
    (see comic-scraper/src/comic_scraper/lookup.py) so the frontend needs no
    source-specific handling.

    GCD is crowd-sourced and can have sparse stub entries - a very recent
    release might have just series/issue/date cataloged, with publisher,
    creator credits, and cover pricing filled in by editors later. Rather
    than committing to a possibly-incomplete GCD-only result, any field GCD
    came back blank on gets backfilled from Metron, via the same
    comic-scraper lookup already needed for the cover image (no extra
    network call - just using more of the one response). Swallows failure
    since a missing image/backfill shouldn't block the add.
    """
    issue = gcd_lookup.find_issue_by_upc(gcd_db, upc12, ean)
    if issue is None:
        return None
    fields = gcd_lookup.get_issue_fields(gcd_db, issue.id)

    result = {
        "series_name": fields.series,
        "issue_number": fields.issue_number or "",
        "legacy_number": fields.legacy_number,
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
        "image": None,
        "cover_hash": None,
    }

    try:
        params = {"ean5": ean} if ean else {}  # comic-scraper's own contract, see note above
        resp = httpx.get(
            f"{settings.comic_scraper_url}/lookup/{upc12}",
            params=params,
            timeout=LOOKUP_TIMEOUT,
        )
        if resp.is_success:
            metron = resp.json()
            result["image"] = metron.get("image")
            for key in (
                "publisher_name", "cover_date", "series_volume", "variant_name",
                "cover_artists", "writers", "pencillers", "inkers", "credits",
                "store_date", "cover_hash", "metron_id", "cv_id",
            ):
                if not result.get(key) and metron.get(key):
                    result[key] = metron[key]
    except httpx.RequestError:
        pass

    return result


@router.post("/lookup/batch")
def lookup_barcode_batch(
    payload: dict,
    gcd_db: Session | None = Depends(get_gcd_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    items = payload.get("items", [])

    def event_stream():
        # GCD first, same as single-item scan (_lookup_gcd) - previously this
        # endpoint skipped GCD entirely and went straight to comic-scraper,
        # unlike every other lookup path in the app. GCD hits stream out
        # immediately; anything left over is re-batched to comic-scraper in
        # one call, with indices translated back to their original position
        # (the frontend places results by event.index, not arrival order, so
        # GCD hits arriving before the comic-scraper batch is fine).
        unresolved: list[tuple[int, dict]] = []
        for index, item in enumerate(items):
            upc12 = item.get("upc12")
            ean = item.get("ean")
            gcd_result = _lookup_gcd(gcd_db, upc12, ean) if gcd_db is not None else None
            if gcd_result is not None:
                event = {"index": index, "upc12": upc12, "ean": ean, "status": "success", "result": gcd_result}
                yield f"data: {json.dumps(event)}\n\n".encode()
            else:
                unresolved.append((index, item))

        if not unresolved:
            return

        # comic-scraper's own batch schema expects each item's add-on under
        # its "ean5" key (external contract, unrelated to comicvault's own
        # "ean" naming) - translated at this boundary rather than renaming
        # comic-scraper itself.
        sub_payload = {
            "items": [{"upc12": item.get("upc12"), "ean5": item.get("ean")} for _, item in unresolved],
        }
        try:
            with httpx.stream(
                "POST",
                f"{settings.comic_scraper_url}/lookup/batch",
                json=sub_payload,
                timeout=None,
            ) as r:
                for line in r.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    event = json.loads(line[len("data: "):])
                    original_index, _ = unresolved[event["index"]]
                    event["index"] = original_index
                    if "ean5" in event:
                        event["ean"] = event.pop("ean5")
                    yield f"data: {json.dumps(event)}\n\n".encode()
        except httpx.RequestError:
            for original_index, item in unresolved:
                event = {
                    "index": original_index, "upc12": item.get("upc12"), "ean": item.get("ean"),
                    "status": "error", "message": "Lookup service unavailable",
                }
                yield f"data: {json.dumps(event)}\n\n".encode()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


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
