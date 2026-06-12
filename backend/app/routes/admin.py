from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud
from app.auth import get_current_admin
from app.database import get_db
from app.models import User
from app.schemas import ComicCreate, ComicOut, UserOut, UserUpdate

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserOut])
def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    return crud.get_all_users(db, skip=skip, limit=limit)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    update: UserUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    if update.is_admin is not None:
        user = crud.set_user_admin(db, user_id, update.is_admin)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    raise HTTPException(status_code=400, detail="Nothing to update")


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    if not crud.delete_user(db, user_id):
        raise HTTPException(status_code=404, detail="User not found")


@router.post("/comics", response_model=ComicOut, status_code=201)
def add_comic(
    comic_in: ComicCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    return crud.create_comic(db, comic_in, user_id=admin.id)


@router.get("/comics", response_model=list[ComicOut])
def list_comics(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    from app.models import Comic
    return db.query(Comic).offset(skip).limit(limit).all()


@router.delete("/comics/{comic_id}", status_code=204)
def delete_comic(
    comic_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    from app.models import Comic
    comic = db.query(Comic).filter(Comic.id == comic_id).first()
    if not comic:
        raise HTTPException(status_code=404, detail="Comic not found")
    db.delete(comic)
    db.commit()
