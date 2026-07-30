import difflib
import random
import re
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from app.auth import hash_password
from app.models import (
    BugReport, CollectionSnapshot, Comic, CSVImport, ExternalIssueCache,
    ExternalSeriesSync, KioskFeaturedSet, KioskSignup, Sale, User, UserComic,
    UserColumnPreference,
)
from app.schemas import (
    BugReportCreate, ComicCreate, ComicUpdate, ExternalIssueSummary,
    SaleCreate, SaleUpdate, UserComicCreate, UserComicUpdate, UserCreate,
)

FEATURED_TTL = timedelta(hours=24)

# --- Default columns shown for each page ---

DEFAULT_COLLECTION_COLUMNS: dict[str, bool] = {
    "upc": True, "img": True, "series": True, "volume": True, "issue_number": True,
    "cover_date": True, "store_date": True, "direct": True, "publisher": True,
    "count": True, "print_run": True, "variant": True, "cover_artist": True,
    "artist": True, "penciller": True, "inker": True, "writer": True,
    "average_price": True, "paid_price": True, "sell_price": True, "buy_date": True,
    "point_of_purchase": True, "signed": True, "remarked": True, "notes": True,
}

DEFAULT_SOLD_COLUMNS: dict[str, bool] = {
    "publisher": True, "series": True, "volume": True, "issue_number": True,
    "writer": True, "sell_date": True, "sell_price": True, "notes": True,
}


# --- Users ---

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def get_all_users(db: Session, skip: int = 0, limit: int = 100) -> list[User]:
    return db.query(User).offset(skip).limit(limit).all()


def create_user(db: Session, user_in: UserCreate) -> User:
    user = User(username=user_in.username, password_hash=hash_password(user_in.password))
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


def set_user_kiosk(db: Session, user_id: int, is_kiosk: bool) -> Optional[User]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    user.is_kiosk = is_kiosk
    db.commit()
    db.refresh(user)
    return user


# --- Comics ---

def get_comic_by_upc(db: Session, upc: str) -> Optional[Comic]:
    return db.query(Comic).filter(Comic.upc == upc).first()


def find_matching_comic(db: Session, data: dict) -> Optional[Comic]:
    q = db.query(Comic).filter(Comic.series == data.get("series"))
    for field in ["publisher", "volume", "issue_number", "variant", "print_run"]:
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
    series: Optional[str] = None,
    publisher: Optional[str] = None,
    writer: Optional[str] = None,
    artist: Optional[str] = None,
    volume: Optional[str] = None,
    issue_number: Optional[str] = None,
    variant: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> list[Comic]:
    q = db.query(Comic)
    if series:
        q = q.filter(Comic.series.ilike(f"%{series}%"))
    if publisher:
        q = q.filter(Comic.publisher.ilike(f"%{publisher}%"))
    if writer:
        q = q.filter(Comic.writer.ilike(f"%{writer}%"))
    if artist:
        q = q.filter(Comic.artist.ilike(f"%{artist}%"))
    if volume:
        q = q.filter(Comic.volume == volume)
    if issue_number:
        q = q.filter(Comic.issue_number == issue_number)
    if variant:
        q = q.filter(Comic.variant.ilike(f"%{variant}%"))
    return q.offset(skip).limit(limit).all()


# --- UserComics ---

def user_already_owns(db: Session, user_id: int, comic_id: int) -> bool:
    return db.query(UserComic).filter(
        UserComic.user_id == user_id,
        UserComic.comic_id == comic_id,
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
    series: Optional[str] = None,
    publisher: Optional[str] = None,
    writer: Optional[str] = None,
    skip: int = 0,
    limit: int = 200,
) -> tuple[list[UserComic], int]:
    q = (
        db.query(UserComic)
        .join(Comic)
        .options(joinedload(UserComic.sales))
        .filter(UserComic.user_id == user_id)
    )
    if series:
        q = q.filter(Comic.series.ilike(f"%{series}%"))
    if publisher:
        q = q.filter(Comic.publisher.ilike(f"%{publisher}%"))
    if writer:
        q = q.filter(Comic.writer.ilike(f"%{writer}%"))
    total = q.count()
    items = q.order_by(Comic.series, Comic.issue_number).offset(skip).limit(limit).all()
    return items, total


def get_kiosk_collection(
    db: Session,
    series: Optional[str] = None,
    publisher: Optional[str] = None,
    skip: int = 0,
    limit: int = 200,
) -> tuple[list[UserComic], int]:
    """Return all UserComics across all users that have at least one available copy."""
    q = (
        db.query(UserComic)
        .join(Comic)
        .options(joinedload(UserComic.sales))
    )
    if series:
        q = q.filter(Comic.series.ilike(f"%{series}%"))
    if publisher:
        q = q.filter(Comic.publisher.ilike(f"%{publisher}%"))
    available = [uc for uc in q.all() if (uc.count or 1) > len(uc.sales)]
    return available[skip:skip + limit], len(available)


def get_sold_collection(
    db: Session,
    user_id: int,
    series: Optional[str] = None,
    publisher: Optional[str] = None,
    skip: int = 0,
    limit: int = 500,
) -> list[Sale]:
    q = (
        db.query(Sale)
        .join(UserComic)
        .join(Comic)
        .options(joinedload(Sale.user_comic).joinedload(UserComic.comic))
        .filter(UserComic.user_id == user_id)
    )
    if series:
        q = q.filter(Comic.series.ilike(f"%{series}%"))
    if publisher:
        q = q.filter(Comic.publisher.ilike(f"%{publisher}%"))
    return q.order_by(Sale.sell_date.desc()).offset(skip).limit(limit).all()


def get_user_comic_by_id(db: Session, user_id: int, uc_id: int) -> Optional[UserComic]:
    return (
        db.query(UserComic)
        .filter(UserComic.id == uc_id, UserComic.user_id == user_id)
        .first()
    )


def set_user_comic_photo(db: Session, user_id: int, uc_id: int, path: str) -> Optional[UserComic]:
    uc = get_user_comic_by_id(db, user_id, uc_id)
    if not uc:
        return None
    uc.personal_img = path
    db.commit()
    db.refresh(uc)
    return uc


def delete_user_comic(db: Session, user_id: int, uc_id: int) -> bool:
    uc = get_user_comic_by_id(db, user_id, uc_id)
    if not uc:
        return False
    db.delete(uc)
    db.commit()
    return True


# --- Sales ---

def create_sale(db: Session, user_id: int, uc_id: int, sale_in: SaleCreate) -> Optional[Sale]:
    uc = get_user_comic_by_id(db, user_id, uc_id)
    if not uc:
        return None
    total_copies = uc.count or 1
    if len(uc.sales) >= total_copies:
        return None  # over-sell guard; caller checks for None
    sale = Sale(
        user_comic_id=uc_id,
        sell_date=sale_in.sell_date,
        sell_price=sale_in.sell_price,
        notes=sale_in.notes,
    )
    db.add(sale)
    db.commit()
    db.refresh(sale)
    return sale


def update_sale(db: Session, user_id: int, uc_id: int, sale_id: int, update: SaleUpdate) -> Optional[Sale]:
    sale = (
        db.query(Sale)
        .join(UserComic)
        .filter(Sale.id == sale_id, Sale.user_comic_id == uc_id, UserComic.user_id == user_id)
        .first()
    )
    if not sale:
        return None
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(sale, field, value)
    db.commit()
    db.refresh(sale)
    return sale


def delete_sale(db: Session, user_id: int, uc_id: int, sale_id: int) -> bool:
    sale = (
        db.query(Sale)
        .join(UserComic)
        .filter(Sale.id == sale_id, Sale.user_comic_id == uc_id, UserComic.user_id == user_id)
        .first()
    )
    if not sale:
        return False
    db.delete(sale)
    db.commit()
    return True


# --- Collection Snapshots ---

def record_snapshot(db: Session, user_id: int) -> None:
    active = (
        db.query(UserComic)
        .options(joinedload(UserComic.sales))
        .join(Comic)
        .filter(UserComic.user_id == user_id)
        .all()
    )
    # Only count UserComics that still have available copies
    available = [uc for uc in active if (uc.count or 1) > len(uc.sales)]
    comic_count = sum(uc.count or 0 for uc in available)
    total_paid = sum((uc.paid_price or 0) * (uc.count or 1) for uc in available)
    total_value = sum((uc.comic.average_price or 0) * (uc.count or 1) for uc in available)

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


# --- Kiosk ---

def upsert_kiosk_signup(db: Session, first_name: str, last_name: str, email: str, phone: Optional[str]) -> KioskSignup:
    conditions = [KioskSignup.email == email]
    if phone:
        conditions.append(KioskSignup.phone == phone)
    existing = db.query(KioskSignup).filter(or_(*conditions)).first()

    if existing is None:
        existing = KioskSignup(first_name=first_name, last_name=last_name, email=email, phone=phone)
        db.add(existing)
    else:
        existing.first_name = first_name
        existing.last_name = last_name
        existing.email = email
        existing.phone = phone

    db.commit()
    db.refresh(existing)
    return existing


def get_fresh_featured_ids(db: Session, section: str) -> Optional[list[int]]:
    row = db.query(KioskFeaturedSet).filter(KioskFeaturedSet.section == section).first()
    if row is None or datetime.utcnow() - row.generated_at > FEATURED_TTL:
        return None
    return list(row.item_ids)


def set_featured_ids(db: Session, section: str, item_ids: list[int]) -> None:
    row = db.query(KioskFeaturedSet).filter(KioskFeaturedSet.section == section).first()
    if row is None:
        row = KioskFeaturedSet(section=section)
        db.add(row)
    row.item_ids = item_ids
    row.generated_at = datetime.utcnow()
    db.commit()


def _available_kiosk_items(q) -> list[UserComic]:
    items = q.options(joinedload(UserComic.sales), joinedload(UserComic.comic)).all()
    return [uc for uc in items if (uc.count or 1) > len(uc.sales)]


def get_kiosk_available_by_price(db: Session, threshold: float, limit: int) -> list[UserComic]:
    q = db.query(UserComic).join(Comic).filter(
        or_(
            UserComic.asking_price > threshold,
            and_(UserComic.asking_price.is_(None), Comic.average_price > threshold),
        )
    )
    available = _available_kiosk_items(q)
    return random.sample(available, min(limit, len(available)))


def get_kiosk_available_signed(db: Session, limit: int) -> list[UserComic]:
    q = db.query(UserComic).join(Comic).filter(UserComic.signed.is_(True))
    available = _available_kiosk_items(q)
    return random.sample(available, min(limit, len(available)))


def get_user_comics_by_ids(db: Session, ids: list[int]) -> list[UserComic]:
    if not ids:
        return []
    rows = (
        db.query(UserComic)
        .join(Comic)
        .options(joinedload(UserComic.sales), joinedload(UserComic.comic))
        .filter(UserComic.id.in_(ids))
        .all()
    )
    by_id = {uc.id: uc for uc in rows if (uc.count or 1) > len(uc.sales)}
    return [by_id[i] for i in ids if i in by_id]


def search_kiosk_series(db: Session, query: str, limit: int = 10) -> list[dict]:
    available = _available_kiosk_items(db.query(UserComic).join(Comic))
    counts: dict[str, int] = {}
    for uc in available:
        counts[uc.comic.series] = counts.get(uc.comic.series, 0) + 1

    normalized_query = re.sub(r"[^a-z0-9]", "", query.strip().lower())
    if not normalized_query:
        return []

    scored: list[tuple[float, str, int]] = []
    for name, count in counts.items():
        normalized_name = re.sub(r"[^a-z0-9]", "", name.lower())
        score = 1.0 if normalized_query in normalized_name else difflib.SequenceMatcher(
            None, normalized_query, normalized_name
        ).ratio()
        if score >= 0.5:
            scored.append((score, name, count))

    scored.sort(key=lambda t: t[0], reverse=True)
    return [{"name": name, "count": count} for _score, name, count in scored[:limit]]


def get_kiosk_items_by_series(db: Session, series_name: str) -> list[UserComic]:
    q = db.query(UserComic).join(Comic).filter(Comic.series == series_name)
    available = _available_kiosk_items(q)

    def issue_sort_key(uc: UserComic) -> tuple[int, str]:
        match = re.search(r"\d+", uc.comic.issue_number or "")
        return (int(match.group()) if match else 0, uc.comic.issue_number or "")

    return sorted(available, key=issue_sort_key)


# --- External series/issue cache (Metron / ComicVine) ---

def issue_number_sort_key(number: Optional[str]) -> tuple[int, str]:
    match = re.search(r"\d+", number or "")
    return (int(match.group()) if match else 0, number or "")


def normalize_issue_number(number: Optional[str]) -> str:
    """Loosely compare issue numbers across providers/user input - "1", "01",
    and " 1 " should all be treated as the same issue."""
    stripped = (number or "").strip().lstrip("0")
    return stripped.lower() or "0"


def _cache_row_to_summary(row: ExternalIssueCache) -> ExternalIssueSummary:
    return ExternalIssueSummary(
        provider=row.provider,
        provider_issue_id=row.provider_issue_id,
        number=row.number,
        cover_date=row.cover_date,
        image=row.image,
    )


def cache_row_to_comic_create(row: ExternalIssueCache) -> ComicCreate:
    return ComicCreate(
        publisher=row.publisher,
        series=row.series or "",
        volume=row.volume,
        issue_number=row.number,
        cover_date=row.cover_date,
        store_date=row.store_date,
        print_run=row.print_run,
        variant=row.variant,
        direct=row.direct,
        writer=row.writer,
        artist=row.artist,
        penciller=row.penciller,
        inker=row.inker,
        cover_artist=row.cover_artist,
        average_price=row.average_price,
        upc=row.upc,
        img=row.image,
    )


def get_series_sync(db: Session, provider: str, provider_series_id: str) -> Optional[ExternalSeriesSync]:
    return (
        db.query(ExternalSeriesSync)
        .filter(ExternalSeriesSync.provider == provider, ExternalSeriesSync.provider_series_id == provider_series_id)
        .first()
    )


def upsert_series_sync(
    db: Session,
    provider: str,
    provider_series_id: str,
    series_name: Optional[str],
    known_issue_count: int,
) -> ExternalSeriesSync:
    sync = get_series_sync(db, provider, provider_series_id)
    if sync is None:
        sync = ExternalSeriesSync(provider=provider, provider_series_id=provider_series_id)
        db.add(sync)
    if series_name:
        sync.series_name = series_name
    sync.known_issue_count = known_issue_count
    sync.synced_at = datetime.utcnow()
    db.commit()
    db.refresh(sync)
    return sync


def get_cached_issues(db: Session, provider: str, provider_series_id: str) -> list[ExternalIssueSummary]:
    rows = (
        db.query(ExternalIssueCache)
        .filter(
            ExternalIssueCache.provider == provider,
            ExternalIssueCache.provider_series_id == provider_series_id,
        )
        .all()
    )
    summaries = [_cache_row_to_summary(r) for r in rows]
    summaries.sort(key=lambda s: issue_number_sort_key(s.number))
    return summaries


def find_cached_issue_by_number(
    db: Session, provider: str, provider_series_id: str, number: str
) -> Optional[ExternalIssueSummary]:
    """Loose (normalized) match against whatever's already cached for this
    series - doesn't depend on the provider's own number filter having
    worked, since that's never been verified against a live provider."""
    target = normalize_issue_number(number)
    for summary in get_cached_issues(db, provider, provider_series_id):
        if normalize_issue_number(summary.number) == target:
            return summary
    return None


def bulk_upsert_issue_summaries(
    db: Session, provider: str, provider_series_id: str, issues: list[ExternalIssueSummary]
) -> None:
    if not issues:
        return
    existing = {
        row.provider_issue_id: row
        for row in db.query(ExternalIssueCache).filter(
            ExternalIssueCache.provider == provider,
            ExternalIssueCache.provider_issue_id.in_([i.provider_issue_id for i in issues]),
        )
    }
    for issue in issues:
        row = existing.get(issue.provider_issue_id)
        if row is None:
            row = ExternalIssueCache(provider=provider, provider_issue_id=issue.provider_issue_id)
            db.add(row)
        row.provider_series_id = provider_series_id
        row.number = issue.number
        row.cover_date = issue.cover_date
        row.image = issue.image
    db.commit()


def get_cached_issue_fields(db: Session, provider: str, provider_issue_id: str) -> Optional[ExternalIssueCache]:
    return (
        db.query(ExternalIssueCache)
        .filter(
            ExternalIssueCache.provider == provider,
            ExternalIssueCache.provider_issue_id == provider_issue_id,
        )
        .first()
    )


def update_issue_cache_fields(
    db: Session, provider: str, provider_issue_id: str, fields: ComicCreate
) -> ExternalIssueCache:
    row = get_cached_issue_fields(db, provider, provider_issue_id)
    if row is None:
        row = ExternalIssueCache(provider=provider, provider_issue_id=provider_issue_id)
        db.add(row)
    row.number = fields.issue_number
    row.cover_date = fields.cover_date.isoformat() if hasattr(fields.cover_date, "isoformat") else fields.cover_date
    row.image = fields.img
    row.publisher = fields.publisher
    row.series = fields.series
    row.volume = fields.volume
    row.store_date = fields.store_date.isoformat() if hasattr(fields.store_date, "isoformat") else fields.store_date
    row.print_run = fields.print_run
    row.variant = fields.variant
    row.direct = fields.direct
    row.writer = fields.writer
    row.artist = fields.artist
    row.penciller = fields.penciller
    row.inker = fields.inker
    row.cover_artist = fields.cover_artist
    row.average_price = fields.average_price
    row.upc = fields.upc
    row.fields_synced = True
    db.commit()
    db.refresh(row)
    return row
