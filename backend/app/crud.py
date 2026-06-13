from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.auth import hash_password
from app.models import (
    BugReport, CollectionSnapshot, Comic, CSVImport,
    User, UserComic, UserColumnPreference,
)
from app.schemas import (
    BugReportCreate, ComicCreate, ComicUpdate,
    UserComicCreate, UserComicUpdate, UserCreate,
)

# --- Default columns shown for each page ---

DEFAULT_COLLECTION_COLUMNS: dict[str, bool] = {
    "publisher": True, "name": True, "volume": True, "number": True,
    "print": True, "cover": True, "variant": True, "direct": True,
    "writer": True, "artist": True, "pencils": True, "inker": True,
    "cover_artist": True, "average_price": True, "print_ratio": True,
    "upc": True, "number_of_books": True, "price_paid": True,
    "point_of_purchase": True, "buy_date": True, "signed": True,
    "remarked": True, "notes": True,
}

DEFAULT_SOLD_COLUMNS: dict[str, bool] = {
    **DEFAULT_COLLECTION_COLUMNS,
    "sell_date": True,
}


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
    q = db.query(Comic).filter(Comic.name == data.get("name"))
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


def update_comic(db: Session, comic_id: int, update: ComicUpdate) -> Optional[Comic]:
    comic = db.query(Comic).filter(Comic.id == comic_id).first()
    if not comic:
        return None
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(comic, field, value)
    db.commit()
    db.refresh(comic)
    return comic


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

def user_already_owns(db: Session, user_id: int, comic_id: int) -> bool:
    return db.query(UserComic).filter(
        UserComic.user_id == user_id,
        UserComic.comic_id == comic_id,
        UserComic.sell_date.is_(None),
    ).first() is not None


def create_user_comic(db: Session, user_id: int, uc_in: UserComicCreate) -> UserComic:
    uc = UserComic(user_id=user_id, **uc_in.model_dump())
    db.add(uc)
    db.commit()
    db.refresh(uc)
    return uc


def update_user_comic(db: Session, user_id: int, uc_id: int, update: UserComicUpdate) -> Optional[UserComic]:
    uc = get_user_comic_by_id(db, user_id, uc_id)
    if not uc:
        return None
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(uc, field, value)
    db.commit()
    db.refresh(uc)
    return uc


def sell_user_comic(db: Session, user_id: int, uc_id: int) -> Optional[UserComic]:
    uc = get_user_comic_by_id(db, user_id, uc_id)
    if not uc:
        return None
    uc.sell_date = datetime.utcnow()
    db.commit()
    db.refresh(uc)
    return uc


def bulk_update_user_comics(db: Session, user_id: int, updates: list[dict]) -> int:
    count = 0
    for item in updates:
        uc = get_user_comic_by_id(db, user_id, item["id"])
        if not uc:
            continue
        for field, value in item["update"].items():
            if value is not None:
                setattr(uc, field, value)
        count += 1
    db.commit()
    return count


def get_user_collection(
    db: Session,
    user_id: int,
    name: Optional[str] = None,
    publisher: Optional[str] = None,
    writer: Optional[str] = None,
    skip: int = 0,
    limit: int = 500,
) -> list[UserComic]:
    q = (
        db.query(UserComic)
        .join(Comic)
        .filter(UserComic.user_id == user_id, UserComic.sell_date.is_(None))
    )
    if name:
        q = q.filter(Comic.name.ilike(f"%{name}%"))
    if publisher:
        q = q.filter(Comic.publisher.ilike(f"%{publisher}%"))
    if writer:
        q = q.filter(Comic.writer.ilike(f"%{writer}%"))
    return q.offset(skip).limit(limit).all()


def get_sold_collection(
    db: Session,
    user_id: int,
    name: Optional[str] = None,
    publisher: Optional[str] = None,
    skip: int = 0,
    limit: int = 500,
) -> list[UserComic]:
    q = (
        db.query(UserComic)
        .join(Comic)
        .filter(UserComic.user_id == user_id, UserComic.sell_date.isnot(None))
    )
    if name:
        q = q.filter(Comic.name.ilike(f"%{name}%"))
    if publisher:
        q = q.filter(Comic.publisher.ilike(f"%{publisher}%"))
    return q.order_by(UserComic.sell_date.desc()).offset(skip).limit(limit).all()


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


# --- Collection Snapshots ---

def record_snapshot(db: Session, user_id: int) -> None:
    active = (
        db.query(UserComic)
        .join(Comic)
        .filter(UserComic.user_id == user_id, UserComic.sell_date.is_(None))
        .all()
    )
    comic_count = sum(uc.number_of_books or 0 for uc in active)
    total_paid = sum((uc.price_paid or 0) * (uc.number_of_books or 1) for uc in active)
    total_value = sum((uc.comic.average_price or 0) * (uc.number_of_books or 1) for uc in active)

    today = date.today()
    existing = (
        db.query(CollectionSnapshot)
        .filter(CollectionSnapshot.user_id == user_id, CollectionSnapshot.date == today)
        .first()
    )
    if existing:
        existing.comic_count = comic_count
        existing.total_paid = total_paid
        existing.total_value = total_value
    else:
        snap = CollectionSnapshot(
            user_id=user_id,
            date=today,
            comic_count=comic_count,
            total_paid=total_paid,
            total_value=total_value,
        )
        db.add(snap)
    db.commit()


def get_user_snapshots(db: Session, user_id: int) -> list[CollectionSnapshot]:
    return (
        db.query(CollectionSnapshot)
        .filter(CollectionSnapshot.user_id == user_id)
        .order_by(CollectionSnapshot.date.asc())
        .all()
    )


# --- Column Preferences ---

def get_column_preference(db: Session, user_id: int, page: str) -> Optional[UserColumnPreference]:
    return (
        db.query(UserColumnPreference)
        .filter(UserColumnPreference.user_id == user_id, UserColumnPreference.page == page)
        .first()
    )


def upsert_column_preference(db: Session, user_id: int, page: str, columns: dict) -> UserColumnPreference:
    pref = get_column_preference(db, user_id, page)
    if pref:
        pref.columns = columns
    else:
        pref = UserColumnPreference(user_id=user_id, page=page, columns=columns)
        db.add(pref)
    db.commit()
    db.refresh(pref)
    return pref


# --- Bug Reports ---

def create_bug_report(db: Session, user_id: int, report_in: BugReportCreate) -> BugReport:
    report = BugReport(user_id=user_id, **report_in.model_dump())
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def get_all_bug_reports(db: Session, resolved: Optional[bool] = None) -> list[BugReport]:
    q = db.query(BugReport).order_by(BugReport.created_at.desc())
    if resolved is not None:
        q = q.filter(BugReport.resolved == resolved)
    return q.all()


def resolve_bug_report(db: Session, report_id: int) -> Optional[BugReport]:
    report = db.query(BugReport).filter(BugReport.id == report_id).first()
    if not report:
        return None
    report.resolved = True
    db.commit()
    db.refresh(report)
    return report


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
