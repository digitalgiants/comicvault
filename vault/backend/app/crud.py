import difflib
import random
import re
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, joinedload

from app.auth import hash_password
from app.models import (
    BugReport, CollectionSnapshot, Comic, CSVImport, CsvImportConflict, ExternalIssueCache,
    ExternalSeriesSearchCache, ExternalSeriesSearchLog, ExternalSeriesSync,
    KioskFeaturedSet, KioskSearchLog, KioskSettings, KioskSignup, RejectedCoverImage, Sale, User,
    UserComic, UserColumnPreference,
)
from app.schemas import (
    BugReportCreate, ComicCreate, ComicUpdate, ExternalIssueSummary,
    ExternalSeriesResult, SaleCreate, SaleUpdate, UserComicCreate,
    UserComicUpdate, UserCreate,
)

SERIES_SEARCH_TTL = timedelta(hours=24)

# The shop's own account - its photo of a comic is always the master image
# for that catalog entry over anyone else's, per crud.recompute_comic_master_photo.
# Was "digitalgiant"; the shop account moved to "drewfert" (Google sign-in).
MASTER_PHOTO_OWNER_USERNAME = "drewfert"

# --- Default columns shown for each page ---

DEFAULT_COLLECTION_COLUMNS: dict[str, bool] = {
    "upc": True, "img": True, "series": True, "volume": True, "issue_number": True,
    "cover_date": True, "store_date": True, "newstand": True, "publisher": True,
    "count": True, "print_run": True, "variant": True, "cover_letter": True, "legacy_number": True, "cover_artist": True,
    "penciller": True, "inker": True, "writer": True,
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
    user = User(
        username=user_in.username, password_hash=hash_password(user_in.password),
        is_collector=user_in.is_collector, has_seen_tour=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def create_google_user(db: Session, email: str) -> User:
    """First-time Google sign-in with no matching account on file - creates
    one with no password (Google is the only way in) and a username derived
    from the email's local part, deduplicated with a numeric suffix if
    that's already taken. New Google accounts are always Collector - the
    same account type the one open signup path (SignupPage.tsx) creates
    today."""
    base = re.sub(r"[^a-zA-Z0-9_.-]", "", email.split("@")[0]).lower() or "user"
    username = base
    suffix = 1
    while get_user_by_username(db, username):
        suffix += 1
        username = f"{base}{suffix}"

    user = User(username=username, password_hash=None, email=email, is_collector=True, has_seen_tour=False)
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
    for field in ["publisher", "volume", "issue_number", "variant", "cover_letter", "print_run"]:
        val = data.get(field)
        if val is not None:
            q = q.filter(getattr(Comic, field) == val)
        else:
            q = q.filter(getattr(Comic, field).is_(None))

    upc = data.get("upc")
    if upc:
        # Different variant printings of the same issue often share every
        # other field (series/volume/issue_number) but have distinct UPCs -
        # a UPC that conflicts with an on-file one always means "different
        # comic," even if variant/print_run weren't filled in to distinguish
        # them. A missing UPC on the existing row is still an open match.
        q = q.filter(or_(Comic.upc == upc, Comic.upc.is_(None)))

    return q.first()


def create_comic(db: Session, comic_in: ComicCreate, user_id: Optional[int] = None) -> Comic:
    comic = Comic(**comic_in.model_dump(), created_by_user_id=user_id)
    db.add(comic)
    db.commit()
    db.refresh(comic)
    return comic


def sync_comicvine_series_issues(
    db: Session, series: str, publisher: Optional[str], issues: list[dict]
) -> dict:
    """Applies a batch of ComicVine issues (each {"issue_number", "image"} -
    callers should only pass issues that actually have an image) into the
    shared catalog: fills a blank img on an existing series+issue_number+
    publisher match, or creates a new comic if none exists. Never overwrites
    an img that's already set, matching this app's merge-safe convention
    elsewhere (publisher fixes, UPC fixes, CSV enrichment)."""
    created = 0
    images_filled = 0
    skipped = 0
    for issue in issues:
        candidate = {
            "series": series,
            "publisher": publisher,
            "issue_number": issue.get("issue_number"),
            "volume": None,
            "variant": None,
            "cover_letter": None,
            "print_run": None,
        }
        match = find_matching_comic(db, candidate)
        if match:
            if match.img:
                skipped += 1
            else:
                match.img = issue.get("image")
                images_filled += 1
        else:
            comic = Comic(
                series=series,
                publisher=publisher,
                issue_number=issue.get("issue_number"),
                img=issue.get("image"),
            )
            db.add(comic)
            created += 1
    db.commit()
    return {"created": created, "images_filled": images_filled, "skipped": skipped}


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


def update_comic_metadata(db: Session, comic_id: int, updates: dict) -> Optional[Comic]:
    comic = db.query(Comic).filter(Comic.id == comic_id).first()
    if not comic:
        return None
    for field, value in updates.items():
        setattr(comic, field, value)
    db.commit()
    db.refresh(comic)
    return comic


# Every field find_matching_comic requires to build an accurate candidate,
# besides series (handled separately in _find_identity_match - see below).
# _COMIC_IDENTITY_FIELDS is the subset used to decide whether an edit needs
# a merge-check at all - issue_number is included because the admin
# legacy-number-split fix (see get_legacy_number_issues) edits it directly;
# series is included because EditComicModal.tsx's GCD-search retitle flow
# edits it; nothing else currently does, but they're real identity fields
# like the rest.
_COMIC_MATCH_FIELDS = ["publisher", "volume", "issue_number", "variant", "cover_letter", "print_run"]
_COMIC_IDENTITY_FIELDS = ["series", "publisher", "volume", "issue_number", "variant", "cover_letter", "print_run"]


def _describe_comic(comic: Comic) -> str:
    parts = [comic.series]
    if comic.volume:
        parts.append(f"Vol. {comic.volume}")
    if comic.issue_number:
        parts.append(f"#{comic.issue_number}")
    label = " ".join(parts)
    return f"{label} ({comic.publisher})" if comic.publisher else label


def _find_identity_match(db: Session, comic: Comic, updates: dict) -> Optional[Comic]:
    """Returns the existing DIFFERENT comic (if any) that `comic` would
    match after applying `updates`. UPC is checked first and on its own -
    it's the strongest identity signal (a real-world barcode identifying
    one specific printing), so an exact UPC match wins even if some other
    field disagrees (e.g. one row has volume filled in and the other
    doesn't). Only falls back to find_matching_comic's series+publisher+
    volume+variant+cover_letter+print_run matching when there's no UPC to
    go on. Returns None if `updates` doesn't touch any identity field, or
    no match is found."""
    if "upc" not in updates and not any(f in updates for f in _COMIC_IDENTITY_FIELDS):
        return None
    effective_upc = updates["upc"] if "upc" in updates else comic.upc
    if effective_upc:
        candidate_by_upc = get_comic_by_upc(db, effective_upc)
        if candidate_by_upc and candidate_by_upc.id != comic.id:
            return candidate_by_upc
    candidate = {"series": updates.get("series", comic.series), "upc": effective_upc}
    for f in _COMIC_MATCH_FIELDS:
        candidate[f] = updates.get(f, getattr(comic, f))
    found = find_matching_comic(db, candidate)
    if found and found.id != comic.id:
        return found
    return None


def _merge_comic_into(db: Session, comic: Comic, match: Comic) -> None:
    """Re-points every UserComic/RejectedCoverImage/CsvImportConflict/
    BugReport off `comic` onto `match`, then deletes `comic` - the old
    duplicate catalog entry disappears, everything moves under the
    pre-existing one. Caller commits."""
    db.query(UserComic).filter(UserComic.comic_id == comic.id).update(
        {"comic_id": match.id}, synchronize_session=False)
    db.query(RejectedCoverImage).filter(RejectedCoverImage.comic_id == comic.id).update(
        {"comic_id": match.id}, synchronize_session=False)
    db.query(CsvImportConflict).filter(CsvImportConflict.comic_id == comic.id).update(
        {"comic_id": match.id}, synchronize_session=False)
    db.query(BugReport).filter(BugReport.comic_id == comic.id).update(
        {"comic_id": match.id}, synchronize_session=False)
    db.delete(comic)


def update_comic_metadata_with_merge(db: Session, comic_id: int, user_id: int, updates: dict) -> tuple[Optional[Comic], Optional[str]]:
    """Same as update_comic_metadata, but for edits that touch UPC or one of
    _COMIC_IDENTITY_FIELDS (e.g. volume): if the edit would make this
    comic's identity match a DIFFERENT existing Comic row, that's a
    duplicate catalog entry waiting to happen (Comic is the shared catalog,
    not per-user - see CLAUDE.md). Instead, merges into the pre-existing
    match (see _merge_comic_into) - the "old card disappears, everything
    moves under the existing entry" behavior.

    Blocked (not merged) if the editing user already separately owns the
    matching comic too - price/notes/signed/condition/etc. all live on the
    per-user UserComic, so which of the two owned copies' values should
    "win" is ambiguous; we don't guess. The error message names the
    specific comic it collided with so the UI can show the user exactly
    what happened, not just a generic failure.

    Returns (comic, error) - on success `error` is None; on a blocked
    collision `comic` is None and `error` is a user-facing message
    identifying the conflicting comic; on not-found both are None, same
    as update_comic_metadata."""
    comic = db.query(Comic).filter(Comic.id == comic_id).first()
    if not comic:
        return None, None

    match = _find_identity_match(db, comic, updates)
    if match:
        if user_already_owns(db, user_id, match.id):
            return None, f"You already own a copy of {_describe_comic(match)} - delete one copy first, then retry."
        _merge_comic_into(db, comic, match)
        db.commit()
        db.refresh(match)
        return match, None

    for field, value in updates.items():
        setattr(comic, field, value)
    db.commit()
    db.refresh(comic)
    return comic, None


def bulk_merge_comic_field(db: Session, comic_id: int, updates: dict) -> tuple[Optional[Comic], Optional[str]]:
    """Admin bulk-operation counterpart to update_comic_metadata_with_merge
    (see e.g. routes/admin.py's publisher-mismatch bulk-apply) - not scoped
    to one acting user, so the self-collision check considers EVERY current
    owner of `comic_id` instead of a single passed-in user, skipping (not
    partially merging) if any of them already separately own the match.
    Returns (comic, error) with the same shape as update_comic_metadata_with_merge."""
    comic = db.query(Comic).filter(Comic.id == comic_id).first()
    if not comic:
        return None, None

    match = _find_identity_match(db, comic, updates)
    if match:
        owners = {row[0] for row in db.query(UserComic.user_id).filter(UserComic.comic_id == comic.id).distinct()}
        colliding = [uid for uid in owners if user_already_owns(db, uid, match.id)]
        if colliding:
            return None, f"{len(colliding)} owner(s) of {_describe_comic(comic)} already own {_describe_comic(match)} - skipped."
        _merge_comic_into(db, comic, match)
        db.commit()
        db.refresh(match)
        return match, None

    for field, value in updates.items():
        setattr(comic, field, value)
    db.commit()
    db.refresh(comic)
    return comic, None


def get_distinct_publishers(db: Session) -> list[tuple[str, int]]:
    """(publisher, comic_count) for every non-null publisher string
    currently in the catalog - the input side of the admin publisher-
    mismatch report (see gcd_lookup.get_publisher_mismatches)."""
    rows = (
        db.query(Comic.publisher, func.count(Comic.id))
        .filter(Comic.publisher.isnot(None))
        .group_by(Comic.publisher)
        .all()
    )
    return [(publisher, count) for publisher, count in rows]


_UPC_SEPARATOR_RE = re.compile(r"[\s-]")


def clean_upc(upc: str) -> Optional[str]:
    """Cleaned version of a stored UPC if it's fixable (a space/hyphen-
    separated 12 or 17-digit value), else None - used both by the malformed-
    UPC report and its single-comic fix action, so they can't drift out of
    sync on what counts as "fixable"."""
    digits = _UPC_SEPARATOR_RE.sub("", upc.strip())
    return digits if digits.isdigit() and len(digits) in (12, 17) else None


def get_malformed_upc_comics(db: Session) -> list[dict]:
    """Comics whose stored UPC isn't a clean 12 or 17-digit string - e.g. a
    value typed/pasted/imported with a space or dash between the UPC and
    5-digit price add-on (as GCD sometimes displays it), which a clean scan
    or lookup will never exact-match again. See the admin UPC Issues report;
    routes/admin.py's fix action applies `suggested_upc` via
    bulk_merge_comic_field, same merge-safe path as everywhere else."""
    comics = db.query(Comic).filter(Comic.upc.isnot(None)).all()
    results = []
    for comic in comics:
        suggested = clean_upc(comic.upc)
        if suggested == comic.upc:
            continue
        results.append({
            "comic_id": comic.id,
            "series": comic.series,
            "issue_number": comic.issue_number,
            "publisher": comic.publisher,
            "upc": comic.upc,
            "suggested_upc": suggested,
        })
    return results


_LEGACY_NUMBER_RE = re.compile(r"^(.*?)\s*\(([^()]+)\)\s*$")


def split_legacy_number(raw: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Splits GCD's combined "1 (685)" issue-number format - a relaunched
    series' new issue number plus its old "legacy" continuous number in
    parentheses - into (issue_number, legacy_number). Returns the value
    unchanged with legacy_number=None if there's no trailing parenthetical
    (the vast majority of issues), so callers can apply this unconditionally
    to any GCD issue.number without a separate has-legacy check."""
    if not raw:
        return raw, None
    match = _LEGACY_NUMBER_RE.match(raw.strip())
    if not match:
        return raw, None
    issue_part, legacy_part = match.group(1).strip(), match.group(2).strip()
    if not issue_part or not legacy_part:
        return raw, None
    return issue_part, legacy_part


def get_legacy_number_issues(db: Session) -> list[dict]:
    """Comics whose issue_number still has GCD's combined "1 (685)" format
    embedded instead of being split into issue_number + legacy_number - e.g.
    from before this split existed, or a CSV import that carried the raw
    GCD string through as-is. See the admin Legacy Numbers report;
    routes/admin.py's fix action applies the split via
    bulk_merge_comic_field, same merge-safe path as everywhere else."""
    comics = db.query(Comic).filter(Comic.issue_number.isnot(None)).all()
    results = []
    for comic in comics:
        issue_part, legacy_part = split_legacy_number(comic.issue_number)
        if legacy_part is None:
            continue
        results.append({
            "comic_id": comic.id,
            "series": comic.series,
            "issue_number": comic.issue_number,
            "publisher": comic.publisher,
            "suggested_issue_number": issue_part,
            "suggested_legacy_number": legacy_part,
        })
    return results


def get_distinct_comic_ids_for_user_comics(db: Session, user_id: int, uc_ids: list[int]) -> list[int]:
    """Distinct Comic ids for the given UserComic ids, scoped to user_id -
    ids that don't exist or don't belong to this user are silently dropped,
    same ownership-check convention as bulk_update_user_comics."""
    rows = (
        db.query(UserComic.comic_id)
        .filter(UserComic.id.in_(uc_ids), UserComic.user_id == user_id)
        .distinct()
        .all()
    )
    return [row[0] for row in rows]


def get_distinct_publishers_for_user_comics(db: Session, user_id: int, uc_ids: list[int]) -> list[Optional[str]]:
    """Distinct Comic.publisher values (including None) among the given
    UserComic ids, scoped to user_id - used to decide whether a bulk-edit
    selection shares one current publisher (see routes/comics.py's
    bulk-publisher/suggest)."""
    rows = (
        db.query(Comic.publisher)
        .join(UserComic, UserComic.comic_id == Comic.id)
        .filter(UserComic.id.in_(uc_ids), UserComic.user_id == user_id)
        .distinct()
        .all()
    )
    return [row[0] for row in rows]


def search_comics(
    db: Session,
    series: Optional[str] = None,
    publisher: Optional[str] = None,
    writer: Optional[str] = None,
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
    changes = update.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(uc, field, value)
    db.commit()
    db.refresh(uc)
    if "personal_img" in changes:
        recompute_comic_master_photo(db, uc.comic_id)
    return uc


def bulk_update_user_comics(db: Session, user_id: int, updates: list[dict]) -> int:
    count = 0
    comics_to_recompute: set[int] = set()
    for item in updates:
        uc = get_user_comic_by_id(db, user_id, item["id"])
        if not uc:
            continue
        for field, value in item["update"].items():
            if value is not None:
                setattr(uc, field, value)
        if "personal_img" in item["update"]:
            comics_to_recompute.add(uc.comic_id)
        count += 1
    db.commit()
    for comic_id in comics_to_recompute:
        recompute_comic_master_photo(db, comic_id)
    return count


def _comic_sort_order():
    """Alphabetical by title, then volume, then issue number. Volume and
    issue_number are stored as strings, so a plain ORDER BY would put "10"
    before "2" - sorting by length first approximates numeric order without
    needing to parse non-numeric values like "Annual" or "1A". Comics
    missing a volume/issue sort after ones that have it (Postgres' default
    NULLS LAST for ascending order)."""
    return (
        func.lower(Comic.series),
        func.length(Comic.volume), Comic.volume,
        func.length(Comic.issue_number), Comic.issue_number,
    )


def get_user_collection(
    db: Session,
    user_id: int,
    series: Optional[str] = None,
    publisher: Optional[str] = None,
    writer: Optional[str] = None,
    issue_number: Optional[str] = None,
    series_exact: Optional[str] = None,
    publisher_exact: Optional[str] = None,
    no_publisher: bool = False,
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
    if issue_number:
        # Exact match, not ilike - "1" shouldn't also pull "10", "11", "21"...
        q = q.filter(Comic.issue_number == issue_number)
    if series_exact:
        # Used by the desktop "drill into a series" view (CollectionPage.tsx) -
        # exact, not ilike, so "Batman" doesn't also pull "Batman Beyond" etc.
        q = q.filter(func.lower(Comic.series) == series_exact.strip().lower())
    if no_publisher:
        q = q.filter(Comic.publisher.is_(None))
    elif publisher_exact:
        q = q.filter(Comic.publisher == publisher_exact)
    total = q.count()
    items = q.order_by(*_comic_sort_order()).offset(skip).limit(limit).all()
    return items, total


def get_user_collection_series_groups(
    db: Session,
    user_id: int,
    series: Optional[str] = None,
    publisher: Optional[str] = None,
    writer: Optional[str] = None,
    skip: int = 0,
    limit: int = 60,
) -> tuple[list[dict], int]:
    """Groups the user's collection by (series, publisher) for the desktop
    "browse by series" landing view (CollectionPage.tsx) - one card per
    series, drilling into get_user_collection(series_exact=...) for the
    full table. Loads the full filtered set into memory and groups in
    Python rather than a SQL GROUP BY, since picking a representative cover
    image per group needs either a window function or a second correlated
    query - for a personal collection's scale, grouping an already-small
    filtered result set in Python is simpler and equally correct.

    Cover image preference: an owned copy of issue #1 wins whenever one has
    a usable image on file (see _issue_one_cover_priority for the exact
    tie-break among multiple #1 printings/variants), falling back to the
    most recently added issue's cover otherwise - same as before this
    preference existed."""
    q = (
        db.query(UserComic)
        .join(Comic)
        .filter(UserComic.user_id == user_id)
    )
    if series:
        q = q.filter(Comic.series.ilike(f"%{series}%"))
    if publisher:
        q = q.filter(Comic.publisher.ilike(f"%{publisher}%"))
    if writer:
        q = q.filter(Comic.writer.ilike(f"%{writer}%"))
    all_items = q.order_by(UserComic.created_at.desc()).all()

    groups: dict[tuple[str, Optional[str]], dict] = {}
    # Lower wins - tracked per group alongside the group dict itself so a
    # later (older, since all_items is newest-first) #1 copy never displaces
    # an already-found better tier, but the first-seen (most recent) copy
    # within the same tier does win.
    best_cover_priority: dict[tuple[str, Optional[str]], int] = {}

    for uc in all_items:
        key = (uc.comic.series, uc.comic.publisher)
        group = groups.get(key)
        if group is None:
            # First hit per key wins as the fallback cover - all_items is
            # already ordered newest-first, so this is the most recently
            # added copy. Overridden below if any owned copy of issue #1
            # turns out to have a usable image.
            group = {
                "series": uc.comic.series,
                "publisher": uc.comic.publisher,
                "issue_count": 0,
                "cover_img": uc.comic.master_photo or uc.comic.img,
                "cover_comic_id": uc.comic.id,
                "cover_issue_number": uc.comic.issue_number,
            }
            groups[key] = group
        group["issue_count"] += 1

        priority = _issue_one_cover_priority(uc.comic)
        if priority is not None and priority < best_cover_priority.get(key, 999):
            best_cover_priority[key] = priority
            group["cover_img"] = uc.comic.master_photo or uc.comic.img
            group["cover_comic_id"] = uc.comic.id
            group["cover_issue_number"] = uc.comic.issue_number

    group_list = sorted(groups.values(), key=lambda g: g["series"].lower())
    total = len(group_list)
    page = group_list[skip: skip + limit]
    return page, total


def _issue_one_cover_priority(comic: Comic) -> Optional[int]:
    """Priority tier for using this comic as its series group's cover image,
    if it's a copy of issue #1 with a usable image on file - lower wins.
    None if this comic isn't a usable #1 cover at all (wrong issue, or no
    image), meaning the caller's normal "most recently added" fallback
    applies instead.

    The regular/non-variant printing wins over an explicit "Cover A", which
    wins over any other cover of #1 - matches this app's existing
    convention that GCD leaves a base printing's variant_name blank rather
    than writing "Cover A" (see gcd_lookup.find_issue_by_series_issue)."""
    if normalize_issue_number(comic.issue_number) != "1":
        return None
    if not (comic.master_photo or comic.img):
        return None
    if not comic.cover_letter and not comic.variant:
        return 0
    if (comic.cover_letter or "").strip().lower() == "a":
        return 1
    return 2


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
        .order_by(*_comic_sort_order())
    )
    if series:
        q = q.filter(Comic.series.ilike(f"%{series}%"))
    if publisher:
        q = q.filter(Comic.publisher.ilike(f"%{publisher}%"))
    available = [uc for uc in q.all() if _is_available_for_sale(uc)]
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


def recompute_comic_master_photo(db: Session, comic_id: int) -> None:
    """A physical photo of the comic is more trustworthy than a looked-up
    stock cover, so it takes priority as the comic's shared image - but the
    original img is left untouched so removing the photo cleanly reverts to
    it. Priority: the shop's own photo (MASTER_PHOTO_OWNER_USERNAME) if it
    owns a copy and has one, else any other owner's photo, else none."""
    comic = db.query(Comic).filter(Comic.id == comic_id).first()
    if comic is None:
        return

    owner_photo = (
        db.query(UserComic.personal_img)
        .join(User, UserComic.user_id == User.id)
        .filter(
            UserComic.comic_id == comic_id,
            User.username == MASTER_PHOTO_OWNER_USERNAME,
            UserComic.personal_img.isnot(None),
        )
        .scalar()
    )
    if owner_photo is None:
        owner_photo = (
            db.query(UserComic.personal_img)
            .filter(UserComic.comic_id == comic_id, UserComic.personal_img.isnot(None))
            .order_by(UserComic.id)
            .limit(1)
            .scalar()
        )

    if comic.master_photo != owner_photo:
        comic.master_photo = owner_photo
        db.commit()


def backfill_master_photos(db: Session) -> None:
    """Idempotent - safe to run on every deploy. Recomputes master_photo for
    every comic that has at least one owner photo on file, in case it's
    missing (new comics with photos) or out of date (photo since removed)."""
    comic_ids = {
        row[0]
        for row in db.query(UserComic.comic_id).filter(UserComic.personal_img.isnot(None)).distinct()
    }
    comic_ids |= {
        row[0]
        for row in db.query(Comic.id).filter(Comic.master_photo.isnot(None))
    }
    for comic_id in comic_ids:
        recompute_comic_master_photo(db, comic_id)


def set_user_comic_photo(db: Session, user_id: int, uc_id: int, path: str) -> Optional[UserComic]:
    uc = get_user_comic_by_id(db, user_id, uc_id)
    if not uc:
        return None
    uc.personal_img = path
    db.commit()
    db.refresh(uc)
    recompute_comic_master_photo(db, uc.comic_id)
    return uc


def delete_user_comic(db: Session, user_id: int, uc_id: int) -> bool:
    uc = get_user_comic_by_id(db, user_id, uc_id)
    if not uc:
        return False
    comic_id = uc.comic_id
    db.delete(uc)
    db.commit()
    recompute_comic_master_photo(db, comic_id)
    return True


# --- Sales ---

def create_sale(db: Session, user_id: int, uc_id: int, sale_in: SaleCreate) -> Optional[Sale]:
    uc = get_user_comic_by_id(db, user_id, uc_id)
    if not uc:
        return None
    if not _is_available_for_sale(uc):
        return None  # over-sell guard (also respects reserve_count/do_not_sell); caller checks for None
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


def update_csv_import_stats(db: Session, import_id: int, **fields) -> Optional[CSVImport]:
    record = db.query(CSVImport).filter(CSVImport.id == import_id).first()
    if not record:
        return None
    for key, value in fields.items():
        setattr(record, key, value)
    db.commit()
    db.refresh(record)
    return record


# --- CSV import GCD-enrichment conflicts (see app.gcd_lookup.enrich_comic_from_gcd) ---

_CSV_CONFLICT_DATE_FIELDS = {"cover_date", "store_date"}
_CSV_CONFLICT_FLOAT_FIELDS = {"average_price"}


def _coerce_csv_conflict_value(field_name: str, raw: Optional[str]):
    if raw is None:
        return None
    if field_name in _CSV_CONFLICT_DATE_FIELDS:
        return date.fromisoformat(raw)
    if field_name in _CSV_CONFLICT_FLOAT_FIELDS:
        return float(raw)
    return raw


def create_csv_conflict(
    db: Session, user_id: int, csv_import_id: Optional[int], comic_id: int,
    field_name: str, csv_value: Optional[str], gcd_value: Optional[str],
) -> CsvImportConflict:
    conflict = CsvImportConflict(
        user_id=user_id,
        csv_import_id=csv_import_id,
        comic_id=comic_id,
        field_name=field_name,
        csv_value=csv_value,
        gcd_value=gcd_value,
    )
    db.add(conflict)
    db.commit()
    db.refresh(conflict)
    return conflict


def get_pending_csv_conflicts(db: Session, user_id: int) -> list[CsvImportConflict]:
    return (
        db.query(CsvImportConflict)
        .filter(CsvImportConflict.user_id == user_id, CsvImportConflict.status == "pending")
        .order_by(CsvImportConflict.created_at.desc())
        .all()
    )


def reject_cover_image(db: Session, comic_id: int, image_url: str) -> None:
    """Idempotent - rejecting the same image twice for the same comic is a
    no-op, not a unique-constraint crash."""
    exists = (
        db.query(RejectedCoverImage)
        .filter(RejectedCoverImage.comic_id == comic_id, RejectedCoverImage.image_url == image_url)
        .first()
    )
    if exists:
        return
    db.add(RejectedCoverImage(comic_id=comic_id, image_url=image_url))
    db.commit()


def get_rejected_cover_images(db: Session, comic_id: int) -> set[str]:
    rows = db.query(RejectedCoverImage.image_url).filter(RejectedCoverImage.comic_id == comic_id).all()
    return {url for (url,) in rows}


def resolve_csv_conflict(db: Session, user_id: int, conflict_id: int, accept: bool) -> tuple[Optional[CsvImportConflict], Optional[str]]:
    """Returns (conflict, error). On a blocked merge (see
    update_comic_metadata_with_merge), the conflict is left "pending" -
    not silently marked "accepted" for a change that didn't happen - and
    `error` names the comic it collided with so the UI can show the user
    what happened, same as the Edit modal's merge errors."""
    conflict = (
        db.query(CsvImportConflict)
        .filter(
            CsvImportConflict.id == conflict_id,
            CsvImportConflict.user_id == user_id,
            CsvImportConflict.status == "pending",
        )
        .first()
    )
    if not conflict:
        return None, None
    if accept:
        value = _coerce_csv_conflict_value(conflict.field_name, conflict.gcd_value)
        _, error = update_comic_metadata_with_merge(db, conflict.comic_id, user_id, {conflict.field_name: value})
        if error:
            return conflict, error
        conflict.status = "accepted"
    else:
        conflict.status = "rejected"
    conflict.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(conflict)
    return conflict, None


# --- Kiosk ---

def get_kiosk_signups(db: Session) -> list[KioskSignup]:
    return db.query(KioskSignup).order_by(KioskSignup.created_at.desc()).all()


def delete_kiosk_signup(db: Session, signup_id: int) -> bool:
    signup = db.query(KioskSignup).filter(KioskSignup.id == signup_id).first()
    if not signup:
        return False
    db.delete(signup)
    db.commit()
    return True


def update_kiosk_signup(db: Session, signup_id: int, updates: dict) -> Optional[KioskSignup]:
    signup = db.query(KioskSignup).filter(KioskSignup.id == signup_id).first()
    if not signup:
        return None
    for field, value in updates.items():
        setattr(signup, field, value)
    db.commit()
    db.refresh(signup)
    return signup


def log_kiosk_search(db: Session, query: str, section: str) -> None:
    db.add(KioskSearchLog(query=query, section=section))
    db.commit()


def get_kiosk_search_logs(db: Session, limit: int = 500) -> list[KioskSearchLog]:
    return db.query(KioskSearchLog).order_by(KioskSearchLog.created_at.desc()).limit(limit).all()


def upsert_kiosk_signup(db: Session, first_name: str, last_name: str, email: str, phone: Optional[str], notes: Optional[str] = None) -> KioskSignup:
    conditions = [KioskSignup.email == email]
    if phone:
        conditions.append(KioskSignup.phone == phone)
    existing = db.query(KioskSignup).filter(or_(*conditions)).first()

    if existing is None:
        existing = KioskSignup(first_name=first_name, last_name=last_name, email=email, phone=phone, notes=notes)
        db.add(existing)
    else:
        existing.first_name = first_name
        existing.last_name = last_name
        existing.email = email
        existing.phone = phone
        existing.notes = notes

    db.commit()
    db.refresh(existing)
    return existing


def get_fresh_featured_ids(db: Session, section: str, ttl_minutes: int) -> Optional[list[int]]:
    row = db.query(KioskFeaturedSet).filter(KioskFeaturedSet.section == section).first()
    if row is None or datetime.utcnow() - row.generated_at > timedelta(minutes=ttl_minutes):
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


def get_kiosk_settings(db: Session) -> KioskSettings:
    row = db.query(KioskSettings).first()
    if row is None:
        row = KioskSettings()
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def update_kiosk_settings(db: Session, **fields) -> KioskSettings:
    row = get_kiosk_settings(db)
    for key, value in fields.items():
        if value is not None:
            setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


def _is_available_for_sale(uc: UserComic) -> bool:
    """True if at least one copy is neither sold, reserved (reserve_count),
    nor fully withheld (do_not_sell). Shared by every kiosk-facing query,
    the cached-featured-id rehydration helper, and the sale-recording
    over-sell guard, so all three enforce the exact same notion of
    "available" - see UserComic.reserve_count / do_not_sell in models.py."""
    return (uc.count or 1) - len(uc.sales) - (uc.reserve_count or 0) > 0 and not uc.do_not_sell


def _available_kiosk_items(q) -> list[UserComic]:
    items = q.options(joinedload(UserComic.sales), joinedload(UserComic.comic)).all()
    return [uc for uc in items if _is_available_for_sale(uc)]


def _kiosk_available_by_price(db: Session, threshold: float) -> list[UserComic]:
    q = db.query(UserComic).join(Comic).filter(
        or_(
            UserComic.asking_price > threshold,
            and_(UserComic.asking_price.is_(None), Comic.average_price > threshold),
        )
    )
    return _available_kiosk_items(q)


def get_kiosk_available_by_price(db: Session, threshold: float, limit: int) -> list[UserComic]:
    available = _kiosk_available_by_price(db, threshold)
    return random.sample(available, min(limit, len(available)))


def get_all_kiosk_available_by_price(db: Session, threshold: float) -> list[UserComic]:
    """Unsampled - the full "Browse All" pool, not just a featured subset."""
    available = _kiosk_available_by_price(db, threshold)
    return sorted(available, key=lambda uc: (uc.comic.series, issue_number_sort_key(uc.comic.issue_number)))


def _kiosk_available_signed(db: Session) -> list[UserComic]:
    q = db.query(UserComic).join(Comic).filter(UserComic.signed.is_(True))
    return _available_kiosk_items(q)


def get_kiosk_available_signed(db: Session, limit: int) -> list[UserComic]:
    available = _kiosk_available_signed(db)
    return random.sample(available, min(limit, len(available)))


def get_all_kiosk_available_signed(db: Session) -> list[UserComic]:
    """Unsampled - the full "Browse All" pool, not just a featured subset."""
    available = _kiosk_available_signed(db)
    return sorted(available, key=lambda uc: (uc.comic.series, issue_number_sort_key(uc.comic.issue_number)))


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
    by_id = {uc.id: uc for uc in rows if _is_available_for_sale(uc)}
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
        newstand=row.newstand,
        writer=row.writer,
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
    row.newstand = fields.newstand
    row.writer = fields.writer
    row.penciller = fields.penciller
    row.inker = fields.inker
    row.cover_artist = fields.cover_artist
    row.average_price = fields.average_price
    row.upc = fields.upc
    row.fields_synced = True
    db.commit()
    db.refresh(row)
    return row


# --- External series-title search cache (Metron / ComicVine) ---

def normalize_search_query(query: str) -> str:
    return re.sub(r"\s+", " ", query.strip().lower())


def get_cached_series_search(
    db: Session, provider: str, normalized_query: str, ignore_ttl: bool = False
) -> Optional[list[ExternalSeriesResult]]:
    """None means "no usable cache" (never searched, or too stale unless
    ignore_ttl). An empty list is a valid cache hit - we searched before and
    found nothing."""
    log = (
        db.query(ExternalSeriesSearchLog)
        .filter(ExternalSeriesSearchLog.provider == provider, ExternalSeriesSearchLog.query == normalized_query)
        .first()
    )
    if log is None:
        return None
    if not ignore_ttl and datetime.utcnow() - log.searched_at > SERIES_SEARCH_TTL:
        return None

    rows = (
        db.query(ExternalSeriesSearchCache)
        .filter(
            ExternalSeriesSearchCache.provider == provider,
            ExternalSeriesSearchCache.query == normalized_query,
        )
        .all()
    )
    return [
        ExternalSeriesResult(
            provider=row.provider,
            provider_series_id=row.provider_series_id,
            name=row.name,
            publisher=row.publisher,
            start_year=row.start_year,
            issue_count=row.issue_count,
            image=row.image,
        )
        for row in rows
    ]


def save_series_search_cache(
    db: Session, provider: str, normalized_query: str, results: list[ExternalSeriesResult]
) -> None:
    db.query(ExternalSeriesSearchCache).filter(
        ExternalSeriesSearchCache.provider == provider,
        ExternalSeriesSearchCache.query == normalized_query,
    ).delete()
    for r in results:
        db.add(ExternalSeriesSearchCache(
            provider=provider,
            query=normalized_query,
            provider_series_id=r.provider_series_id,
            name=r.name,
            publisher=r.publisher,
            start_year=r.start_year,
            issue_count=r.issue_count,
            image=r.image,
        ))

    log = (
        db.query(ExternalSeriesSearchLog)
        .filter(ExternalSeriesSearchLog.provider == provider, ExternalSeriesSearchLog.query == normalized_query)
        .first()
    )
    if log is None:
        log = ExternalSeriesSearchLog(provider=provider, query=normalized_query)
        db.add(log)
    log.searched_at = datetime.utcnow()
    db.commit()
