from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import crud
from app.auth import get_current_non_kiosk, get_current_user
from app.database import get_db
from app.models import User
from app.schemas import (
    BulkUpdateRequest, ComicOut, SaleCreate, SaleOut,
    SaleWithComicOut, UserComicCreate, UserComicOut, UserComicUpdate,
)

router = APIRouter(prefix="/comics", tags=["comics"])


@router.get("/", response_model=list[ComicOut])
def search_comics(
    name: str | None = Query(None),
    publisher: str | None = Query(None),
    writer: str | None = Query(None),
    artist: str | None = Query(None),
    volume: str | None = Query(None),
    number: str | None = Query(None),
    variant: str | None = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_non_kiosk),
):
    return crud.search_comics(db, name=name, publisher=publisher, writer=writer,
                               artist=artist, volume=volume, number=number,
                               variant=variant, skip=skip, limit=limit)


@router.get("/collection", response_model=list[UserComicOut])
def get_my_collection(
    name: str | None = Query(None),
    publisher: str | None = Query(None),
    writer: str | None = Query(None),
    skip: int = 0,
    limit: int = 500,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.is_kiosk:
        return crud.get_kiosk_collection(db, name=name, publisher=publisher, skip=skip, limit=limit)
    return crud.get_user_collection(db, current_user.id, name=name,
                                    publisher=publisher, writer=writer,
                                    skip=skip, limit=limit)


@router.get("/sold", response_model=list[SaleWithComicOut])
def get_sold_collection(
    name: str | None = Query(None),
    publisher: str | None = Query(None),
    skip: int = 0,
    limit: int = 500,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    sales = crud.get_sold_collection(db, current_user.id, name=name,
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
