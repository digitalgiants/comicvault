from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import crud
from app.auth import get_current_user
from app.database import get_db
from app.models import User
from app.schemas import (
    BulkUpdateRequest, ComicOut, UserComicCreate,
    UserComicOut, UserComicUpdate,
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
    _: User = Depends(get_current_user),
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
    return crud.get_user_collection(db, current_user.id, name=name,
                                    publisher=publisher, writer=writer,
                                    skip=skip, limit=limit)


@router.get("/sold", response_model=list[UserComicOut])
def get_sold_collection(
    name: str | None = Query(None),
    publisher: str | None = Query(None),
    skip: int = 0,
    limit: int = 500,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return crud.get_sold_collection(db, current_user.id, name=name,
                                    publisher=publisher, skip=skip, limit=limit)


@router.put("/collection/{uc_id}", response_model=UserComicOut)
def update_user_comic(
    uc_id: int,
    update: UserComicUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    uc = crud.update_user_comic(db, current_user.id, uc_id, update)
    if not uc:
        raise HTTPException(status_code=404, detail="Not found")
    crud.record_snapshot(db, current_user.id)
    return uc


@router.patch("/collection/{uc_id}/sell", response_model=UserComicOut)
def sell_comic(
    uc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    uc = crud.sell_user_comic(db, current_user.id, uc_id)
    if not uc:
        raise HTTPException(status_code=404, detail="Not found")
    crud.record_snapshot(db, current_user.id)
    return uc


@router.post("/collection/bulk", response_model=dict)
def bulk_update(
    req: BulkUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    updates = [{"id": item.id, "update": item.update.model_dump(exclude_unset=True)} for item in req.updates]
    count = crud.bulk_update_user_comics(db, current_user.id, updates)
    crud.record_snapshot(db, current_user.id)
    return {"updated": count}


@router.delete("/collection/{uc_id}", status_code=204)
def remove_from_collection(
    uc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not crud.delete_user_comic(db, current_user.id, uc_id):
        raise HTTPException(status_code=404, detail="Not found")
    crud.record_snapshot(db, current_user.id)
