from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import crud
from app.auth import get_current_user
from app.database import get_db
from app.models import User
from app.schemas import ComicOut, UserComicCreate, UserComicOut

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
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return crud.get_user_collection(db, current_user.id, name=name,
                                    publisher=publisher, writer=writer,
                                    skip=skip, limit=limit)


@router.delete("/collection/{uc_id}", status_code=204)
def remove_from_collection(
    uc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not crud.delete_user_comic(db, current_user.id, uc_id):
        raise HTTPException(status_code=404, detail="Not found")
