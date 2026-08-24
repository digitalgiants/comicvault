import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, File
from sqlalchemy.orm import Session

from app import crud
from app.auth import get_current_non_kiosk, get_current_user
from app.database import get_db
from app.models import User
from app.schemas import (
    BulkUpdateRequest, ComicMetadataUpdate, ComicOut, SaleCreate, SaleOut,
    SaleUpdate, SaleWithComicOut, SeriesGroupOut, UserComicCreate, UserComicOut, UserComicUpdate,
)

router = APIRouter(prefix="/comics", tags=["comics"])

PHOTO_DIR = Path("/app/uploads/personal_img")
PHOTO_DIR.mkdir(parents=True, exist_ok=True)
MAX_PHOTO_SIZE = 3 * 1024 * 1024  # 3MB
MIN_PHOTO_SIZE = 2 * 1024  # 2KB - a real cropped cover photo is well above this; smaller is a blank/corrupt capture
ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.get("/", response_model=list[ComicOut])
def search_comics(
    series: str | None = Query(None),
    publisher: str | None = Query(None),
    writer: str | None = Query(None),
    volume: str | None = Query(None),
    issue_number: str | None = Query(None),
    variant: str | None = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_non_kiosk),
):
    return crud.search_comics(db, series=series, publisher=publisher, writer=writer,
                               volume=volume, issue_number=issue_number,
                               variant=variant, skip=skip, limit=limit)


@router.patch("/{comic_id}/metadata", response_model=ComicOut)
def update_comic_metadata(
    comic_id: int,
    update: ComicMetadataUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    if crud.get_comic_by_id(db, comic_id) is None:
        raise HTTPException(status_code=404, detail="Comic not found")

    data = update.model_dump(exclude_unset=True)
    if "upc" in data:
        normalized = data["upc"].strip() if data["upc"] else None
        data["upc"] = normalized
        if normalized:
            existing = crud.get_comic_by_upc(db, normalized)
            if existing and existing.id != comic_id:
                raise HTTPException(status_code=400, detail="That UPC is already assigned to another comic")
    if "cover_artist" in data:
        data["cover_artist"] = data["cover_artist"].strip() if data["cover_artist"] else None
    if "volume" in data:
        data["volume"] = data["volume"].strip() if data["volume"] else None

    comic, error = crud.update_comic_metadata_with_merge(db, comic_id, current_user.id, data)
    if error:
        raise HTTPException(status_code=400, detail=error)
    return comic


@router.get("/collection", response_model=list[UserComicOut])
def get_my_collection(
    response: Response,
    series: str | None = Query(None),
    publisher: str | None = Query(None),
    writer: str | None = Query(None),
    issue_number: str | None = Query(None),
    series_exact: str | None = Query(None),
    publisher_exact: str | None = Query(None),
    no_publisher: bool = Query(False),
    skip: int = 0,
    limit: int = 200,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.is_kiosk:
        items, total = crud.get_kiosk_collection(db, series=series, publisher=publisher, skip=skip, limit=limit)
    else:
        items, total = crud.get_user_collection(db, current_user.id, series=series,
                                        publisher=publisher, writer=writer,
                                        issue_number=issue_number,
                                        series_exact=series_exact, publisher_exact=publisher_exact,
                                        no_publisher=no_publisher,
                                        skip=skip, limit=limit)
    response.headers["X-Total-Count"] = str(total)
    return items


@router.get("/collection/groups", response_model=list[SeriesGroupOut])
def get_my_collection_series_groups(
    response: Response,
    series: str | None = Query(None),
    publisher: str | None = Query(None),
    writer: str | None = Query(None),
    skip: int = 0,
    limit: int = 60,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    items, total = crud.get_user_collection_series_groups(db, current_user.id, series=series,
                                                            publisher=publisher, writer=writer,
                                                            skip=skip, limit=limit)
    response.headers["X-Total-Count"] = str(total)
    return items


@router.get("/sold", response_model=list[SaleWithComicOut])
def get_sold_collection(
    series: str | None = Query(None),
    publisher: str | None = Query(None),
    skip: int = 0,
    limit: int = 500,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    sales = crud.get_sold_collection(db, current_user.id, series=series,
                                     publisher=publisher, skip=skip, limit=limit)
    return [
        SaleWithComicOut(
            id=s.id,
            user_comic_id=s.user_comic_id,
            sell_date=s.sell_date,
            sell_price=s.sell_price,
            notes=s.notes,
            created_at=s.created_at,
            comic=s.user_comic.comic,
        )
        for s in sales
    ]


@router.put("/collection/{uc_id}", response_model=UserComicOut)
def update_user_comic(
    uc_id: int,
    update: UserComicUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    uc = crud.update_user_comic(db, current_user.id, uc_id, update)
    if not uc:
        raise HTTPException(status_code=404, detail="Not found")
    crud.record_snapshot(db, current_user.id)
    return uc


@router.post("/collection/bulk", response_model=dict)
def bulk_update(
    req: BulkUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    updates = [{"id": item.id, "update": item.update.model_dump(exclude_unset=True)} for item in req.updates]
    count = crud.bulk_update_user_comics(db, current_user.id, updates)
    crud.record_snapshot(db, current_user.id)
    return {"updated": count}


@router.delete("/collection/{uc_id}", status_code=204)
def remove_from_collection(
    uc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    if not crud.delete_user_comic(db, current_user.id, uc_id):
        raise HTTPException(status_code=404, detail="Not found")
    crud.record_snapshot(db, current_user.id)


@router.post("/collection/{uc_id}/photo", response_model=UserComicOut)
async def upload_photo(
    uc_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    if not crud.get_user_comic_by_id(db, current_user.id, uc_id):
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

    uc = crud.set_user_comic_photo(db, current_user.id, uc_id, f"/uploads/personal_img/{filename}")
    return uc


@router.post("/collection/{uc_id}/sales", response_model=SaleOut, status_code=201)
def record_sale(
    uc_id: int,
    sale_in: SaleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    sale = crud.create_sale(db, current_user.id, uc_id, sale_in)
    if sale is None:
        uc = crud.get_user_comic_by_id(db, current_user.id, uc_id)
        if not uc:
            raise HTTPException(status_code=404, detail="Not found")
        raise HTTPException(status_code=400, detail="All copies of this comic have already been sold.")
    crud.record_snapshot(db, current_user.id)
    return sale


@router.put("/collection/{uc_id}/sales/{sale_id}", response_model=SaleOut)
def update_sale(
    uc_id: int,
    sale_id: int,
    update: SaleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    sale = crud.update_sale(db, current_user.id, uc_id, sale_id, update)
    if not sale:
        raise HTTPException(status_code=404, detail="Sale record not found")
    crud.record_snapshot(db, current_user.id)
    return sale


@router.delete("/collection/{uc_id}/sales/{sale_id}", status_code=204)
def delete_sale(
    uc_id: int,
    sale_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    if not crud.delete_sale(db, current_user.id, uc_id, sale_id):
        raise HTTPException(status_code=404, detail="Sale record not found")
    crud.record_snapshot(db, current_user.id)
