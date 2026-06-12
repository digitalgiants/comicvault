from typing import Optional

from sqlalchemy.orm import Session

from app.auth import hash_password
from app.models import Comic, CSVImport, User, UserComic
from app.schemas import ComicCreate, UserComicCreate, UserCreate


# --- Users ---

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def get_all_users(db: Session, skip: int = 0, limit: int = 100) -> list[User]:
    return db.query(User).offset(skip).limit(limit).all()


def create_user(db: Session, user_in: UserCreate) -> User:
    user = User(email=user_in.email, password_hash=hash_password(user_in.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user_id: int) -> bool:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False
    db.delete(user)
    db.commit()
    return True


def set_user_admin(db: Session, user_id: int, is_admin: bool) -> Optional[User]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    user.is_admin = is_admin
    db.commit()
    db.refresh(user)
    return user


# --- Comics ---

def find_matching_comic(db: Session, data: dict) -> Optional[Comic]:
    """Match by (publisher, name, volume, number, variant, print)."""
    q = db.query(Comic).filter(
        Comic.name == data.get("name"),
    )
    for field in ["publisher", "volume", "number", "variant", "print"]:
        val = data.get(field)
        if val is not None:
            q = q.filter(getattr(Comic, field) == val)
        else:
            q = q.filter(getattr(Comic, field).is_(None))
    return q.first()


def create_comic(db: Session, comic_in: ComicCreate, user_id: Optional[int] = None) -> Comic:
    comic = Comic(**comic_in.model_dump(), created_by_user_id=user_id)
    db.add(comic)
    db.commit()
    db.refresh(comic)
    return comic


def get_comic_by_id(db: Session, comic_id: int) -> Optional[Comic]:
    return db.query(Comic).filter(Comic.id == comic_id).first()


def search_comics(
    db: Session,
    name: Optional[str] = None,
    publisher: Optional[str] = None,
    writer: Optional[str] = None,
    artist: Optional[str] = None,
    volume: Optional[str] = None,
    number: Optional[str] = None,
    variant: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> list[Comic]:
    q = db.query(Comic)
    if name:
        q = q.filter(Comic.name.ilike(f"%{name}%"))
    if publisher:
        q = q.filter(Comic.publisher.ilike(f"%{publisher}%"))
    if writer:
        q = q.filter(Comic.writer.ilike(f"%{writer}%"))
    if artist:
        q = q.filter(Comic.artist.ilike(f"%{artist}%"))
    if volume:
        q = q.filter(Comic.volume == volume)
    if number:
        q = q.filter(Comic.number == number)
    if variant:
        q = q.filter(Comic.variant.ilike(f"%{variant}%"))
    return q.offset(skip).limit(limit).all()


# --- UserComics ---

def create_user_comic(db: Session, user_id: int, uc_in: UserComicCreate) -> UserComic:
    uc = UserComic(user_id=user_id, **uc_in.model_dump())
    db.add(uc)
    db.commit()
    db.refresh(uc)
    return uc


def get_user_collection(
    db: Session,
    user_id: int,
    name: Optional[str] = None,
    publisher: Optional[str] = None,
    writer: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> list[UserComic]:
    q = (
        db.query(UserComic)
        .join(Comic)
        .filter(UserComic.user_id == user_id)
    )
    if name:
        q = q.filter(Comic.name.ilike(f"%{name}%"))
    if publisher:
        q = q.filter(Comic.publisher.ilike(f"%{publisher}%"))
    if writer:
        q = q.filter(Comic.writer.ilike(f"%{writer}%"))
    return q.offset(skip).limit(limit).all()


def get_user_comic_by_id(db: Session, user_id: int, uc_id: int) -> Optional[UserComic]:
    return (
        db.query(UserComic)
        .filter(UserComic.id == uc_id, UserComic.user_id == user_id)
        .first()
    )


def delete_user_comic(db: Session, user_id: int, uc_id: int) -> bool:
    uc = get_user_comic_by_id(db, user_id, uc_id)
    if not uc:
        return False
    db.delete(uc)
    db.commit()
    return True


# --- CSV Imports ---

def create_csv_import(db: Session, user_id: int, filename: str, total: int, success: int, failed: int, errors: list) -> CSVImport:
    record = CSVImport(
        user_id=user_id,
        filename=filename,
        total_rows=total,
        successful_imports=success,
        failed_rows=failed,
        error_log=errors,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_user_csv_imports(db: Session, user_id: int) -> list[CSVImport]:
    return db.query(CSVImport).filter(CSVImport.user_id == user_id).order_by(CSVImport.created_at.desc()).all()
