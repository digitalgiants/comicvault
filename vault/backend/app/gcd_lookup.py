"""GCD-first comic lookup: barcode matching and series/issue search against
the local `gcd` database (see app.gcd_database / app.gcd_models). Callers
(routes/scan.py, routes/search.py) treat a None/empty result the same as a
cache miss and fall through to the existing Metron/ComicVine lookup path.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Iterable

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.crud import (
    get_comic_by_upc, get_distinct_publishers, normalize_issue_number, normalize_search_query,
    split_legacy_number,
)
from app.gcd_models import Issue, Publisher, Series, Story, StoryType
from app.schemas import ComicCreate, ExternalIssueSummary, ExternalSeriesResult

SEARCH_LIMIT = 20
COMIC_STORY_TYPE = "comic story"

# Fields get_issue_fields() actually populates from GCD - the set CSV import
# enrichment (enrich_comic_from_gcd) considers filling/comparing. Excludes
# series/issue_number (used for matching itself) and the fields GCD never
# supplies (print_run, newstand, cover_artist, img). legacy_number is
# derived from issue_number itself (see split_legacy_number), not a
# separate GCD field, but is still fair game to blank-fill.
ENRICHABLE_FIELDS = [
    "publisher", "volume", "cover_date", "store_date",
    "variant", "writer", "penciller", "inker", "average_price", "upc", "legacy_number",
]

_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_USD_PRICE_RE = re.compile(r"(\d+\.\d{2})\s*USD", re.IGNORECASE)
_ANY_PRICE_RE = re.compile(r"(\d+\.\d{2})")


def _clean_barcode_digits(barcode: str) -> str:
    """GCD sometimes separates the UPC and price-supplement groups with a
    space or hyphen instead of concatenating them directly (e.g.
    "070989312260 21200" rather than "07098931226021200") - stripped before
    validating/comparing, so both forms extract/match the same UPC."""
    return re.sub(r"[\s-]", "", barcode.strip())


def _extract_upc(barcode: str | None) -> str | None:
    """The forward direction of find_issue_by_upc's own logic: GCD's barcode
    field stores a bare 12-digit UPC, a UPC + 5-digit price supplement (17
    digits, possibly space/hyphen-separated - see _clean_barcode_digits), an
    ISBN-based barcode (18 digits, "978..." prefix - not a real UPC,
    excluded), or sometimes blank/non-numeric junk. When present, the UPC is
    always the leading 12 digits."""
    if not barcode:
        return None
    digits = _clean_barcode_digits(barcode)
    if not digits.isdigit() or len(digits) < 12:
        return None
    if digits.startswith("978") and len(digits) == 18:
        return None
    return digits[:12]


def find_issue_by_upc(gcd_db: Session, upc12: str) -> Issue | None:
    """Matches gcd_issue.barcode against a scanned 12-digit UPC.

    GCD's barcode field stores either a bare 12-digit UPC, or UPC + 5-digit
    price supplement, concatenated or space/hyphen-separated (see
    _clean_barcode_digits) - either way the UPC is the leading 12 digits, so
    a prefix match covers all of these. ISBN-based barcodes (18 digits,
    "978..." prefix) are intentionally excluded - a scanned code is never 13
    digits, so they'd never match a 12-digit prefix anyway.

    Multiple matches (e.g. shared UPCs across variant printings) prefer an
    exact-length match over a prefix match, else the lowest id, rather than
    treating it as ambiguous - GCD is meant to be authoritative here.
    """
    candidates = gcd_db.query(Issue).filter(Issue.barcode.like(f"{upc12}%")).all()
    if not candidates:
        return None
    for issue in candidates:
        if _clean_barcode_digits(issue.barcode) == upc12:
            return issue
    return min(candidates, key=lambda i: i.id)


def find_issue_by_series_issue(
    gcd_db: Session, series: str, issue_number: str, publisher: str | None = None, cover_letter: str | None = None
) -> Issue | None:
    """Exact (case-insensitive) series+issue match against GCD - used by CSV
    import enrichment, deliberately NOT the fuzzy/similarity matching
    search_series() does, since this runs unattended across a whole import
    batch with no per-row review. If publisher is given, it must match too
    (disambiguates two different publishers having a same-named series);
    SQL narrows to one series' issues first, then a small Python loop
    handles issue-number normalization (zero-padding etc. - not expressible
    as a plain SQL comparison).

    GCD often stores different covers of the same issue as separate rows
    sharing one issue_number, distinguished only by its own free-text
    variant_name (e.g. "Cover B") - without cover_letter to disambiguate,
    whichever row the query happens to return first wins, which can
    silently enrich a row with the wrong cover's metadata. cover_letter
    narrows to the row whose variant_name contains "cover <letter>"; "A"
    additionally matches the base printing (variant_of_id is None), since
    GCD leaves that one's variant_name blank rather than writing "Cover A".
    Falls back to the first match if nothing lines up - a best-effort
    match still beats leaving the row entirely unenriched.
    """
    q = gcd_db.query(Issue).join(Series, Issue.series_id == Series.id).filter(
        func.lower(Series.name) == series.strip().lower()
    )
    if publisher:
        q = q.join(Publisher, Series.publisher_id == Publisher.id).filter(
            func.lower(Publisher.name) == publisher.strip().lower()
        )
    target = normalize_issue_number(issue_number)
    matches = [
        issue for issue in q.all()
        if normalize_issue_number(split_legacy_number(issue.number)[0]) == target
    ]
    if not matches:
        return None

    if cover_letter and len(matches) > 1:
        letter = cover_letter.strip().lower()
        needle = f"cover {letter}"
        for issue in matches:
            if issue.variant_name and needle in issue.variant_name.lower():
                return issue
        if letter == "a":
            base = next((i for i in matches if not i.variant_of_id), None)
            if base:
                return base

    return matches[0]


def enrich_comic_from_gcd(db: Session, gcd_db: Session, comic_data: dict) -> tuple[list[tuple[str, str, str]], bool]:
    """Attempts to enrich a CSV-import row (comic_data, keyed like ComicCreate
    fields) from GCD before the Comic is created - tries UPC first, then an
    exact series+issue match if that fails or there's no UPC. Only ever
    called for brand-new comics (an existing catalog match is never touched).

    comic_data is mutated in place: any field that's blank gets filled
    directly from GCD, no review needed. A field that's already set to
    something DIFFERENT than GCD's value is never overwritten - instead
    it's returned as a conflict for the caller to queue for manual
    accept/reject (see crud.create_csv_conflict).

    Returns (conflicts, found) where conflicts is a list of
    (field_name, csv_value, gcd_value) tuples (as strings, for storage) and
    found is whether any GCD match was located at all - False drives the
    "Declined Imports" report for rows GCD has nothing on.
    """
    issue = None
    upc = comic_data.get("upc")
    if upc:
        issue = find_issue_by_upc(gcd_db, upc)
    if issue is None and comic_data.get("series") and comic_data.get("issue_number"):
        issue = find_issue_by_series_issue(
            gcd_db, comic_data["series"], comic_data["issue_number"],
            comic_data.get("publisher"), comic_data.get("cover_letter"),
        )
    if issue is None:
        return [], False

    fields = get_issue_fields(gcd_db, issue.id)
    conflicts: list[tuple[str, str, str]] = []
    for field in ENRICHABLE_FIELDS:
        gcd_val = getattr(fields, field)
        if gcd_val is None:
            continue
        # GCD documents UPCs sometimes shared across reprints/variants (see
        # find_issue_by_upc), and Comic.upc is unique - blank-filling one
        # already claimed by another comic would crash the row's insert.
        # Silently skipping it (leaving upc blank) fits this feature's
        # "never surprise/crash an unattended batch" design better than
        # erroring the whole import over one field on one row.
        if field == "upc" and get_comic_by_upc(db, gcd_val) is not None:
            continue
        csv_val = comic_data.get(field)
        if csv_val is None or csv_val == "":
            comic_data[field] = gcd_val
        elif str(csv_val) != str(gcd_val):
            conflicts.append((field, str(csv_val), str(gcd_val)))
    return conflicts, True


def search_series(
    gcd_db: Session, query: str, limit: int = SEARCH_LIMIT, offset: int = 0
) -> tuple[list[ExternalSeriesResult], int]:
    """Returns (page of results, total matching count). GCD's series table is
    exhaustive - a plain substring match on a common word like "batman" pulls
    in every tie-in/team-up/reprint title containing it anywhere, and a plain
    alphabetical sort can bury (or, under the old hard 20-row cap, entirely
    hide) the actual flagship series behind those. Rank exact match, then
    starts-with, then contains-elsewhere, alphabetical within each tier."""
    normalized = normalize_search_query(query)
    if not normalized:
        return [], 0

    name_lower = func.lower(Series.name)
    rank = case(
        (name_lower == normalized, 0),
        (name_lower.like(f"{normalized}%"), 1),
        else_=2,
    )
    base_q = (
        gcd_db.query(Series, Publisher)
        .join(Publisher, Series.publisher_id == Publisher.id)
        .filter(Series.name.ilike(f"%{normalized}%"))
    )
    total = base_q.count()
    rows = (
        base_q.order_by(rank, Series.name)
        .offset(offset)
        .limit(limit)
        .all()
    )
    results = [
        ExternalSeriesResult(
            provider="gcd",
            provider_series_id=str(series.id),
            name=series.name,
            publisher=publisher.name,
            start_year=series.year_began,
            issue_count=series.issue_count,
            image=None,
        )
        for series, publisher in rows
    ]
    return results, total


def get_series_issues(gcd_db: Session, series_id: int, number: str | None = None) -> list[ExternalIssueSummary]:
    issues = gcd_db.query(Issue).filter(Issue.series_id == series_id).all()
    # Split before matching/returning - GCD's raw issue.number sometimes has
    # a "legacy" continuous number embedded (e.g. "1 (685)" for a relaunched
    # series), which would never match a plain "1" typed by the user or
    # carried in from a CSV row (see split_legacy_number).
    split = [(issue, *split_legacy_number(issue.number)) for issue in issues]
    if number:
        target = normalize_issue_number(number)
        split = [(issue, num, legacy) for issue, num, legacy in split if normalize_issue_number(num) == target]
    return [
        ExternalIssueSummary(
            provider="gcd",
            provider_issue_id=str(issue.id),
            number=num or None,
            legacy_number=legacy,
            cover_date=issue.key_date or None,
            image=None,
        )
        for issue, num, legacy in split
    ]


def get_issue_fields(gcd_db: Session, issue_id: int) -> ComicCreate:
    row = (
        gcd_db.query(Issue, Series, Publisher)
        .join(Series, Issue.series_id == Series.id)
        .join(Publisher, Series.publisher_id == Publisher.id)
        .filter(Issue.id == issue_id)
        .first()
    )
    if row is None:
        raise ValueError(f"No GCD issue with id {issue_id}")
    issue, series, publisher = row

    stories = (
        gcd_db.query(Story)
        .join(StoryType, Story.type_id == StoryType.id)
        .filter(Story.issue_id == issue.id, StoryType.name == COMIC_STORY_TYPE)
        .order_by(Story.sequence_number)
        .all()
    )
    writer = _join_credits(s.script for s in stories)
    penciller = _join_credits(s.pencils for s in stories)
    inker = _join_credits(s.inks for s in stories)
    issue_number, legacy_number = split_legacy_number(issue.number)

    return ComicCreate(
        publisher=publisher.name,
        series=series.name,
        volume=issue.volume or None,
        issue_number=issue_number,
        legacy_number=legacy_number,
        cover_date=_parse_gcd_date(issue.key_date),
        store_date=_parse_gcd_date(issue.on_sale_date),
        print_run=None,
        variant=(issue.variant_name or None) if issue.variant_of_id else None,
        cover_letter=None,
        newstand=None,
        writer=writer,
        penciller=penciller,
        inker=inker,
        cover_artist=None,
        average_price=_parse_gcd_price(issue.price),
        upc=_extract_upc(issue.barcode),
        img=None,
    )


def _join_credits(values: Iterable[str]) -> str | None:
    names = [v.strip() for v in values if v and v.strip()]
    return ", ".join(dict.fromkeys(names)) or None


def _parse_gcd_date(value: str | None) -> date | None:
    """GCD dates are "YYYY-MM-DD" with "00" for an unknown month/day."""
    if not value:
        return None
    match = _DATE_RE.match(value.strip())
    if not match:
        return None
    year, month, day = int(match.group(1)), int(match.group(2)) or 1, int(match.group(3)) or 1
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _parse_gcd_price(value: str | None) -> float | None:
    """GCD's price field is free text, sometimes multiple currencies
    (e.g. "3.99 USD; 4.99 CAD") - best-effort: prefer an explicit USD value,
    else the first decimal number found."""
    if not value:
        return None
    match = _USD_PRICE_RE.search(value) or _ANY_PRICE_RE.search(value)
    return float(match.group(1)) if match else None


def _escape_like(value: str) -> str:
    """Escapes SQL LIKE/ILIKE wildcards in user-controlled text before it's
    interpolated into a pattern - a publisher name containing a literal %
    or _ would otherwise silently change what the pattern matches."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def suggest_gcd_publisher(gcd_db: Session, local_publisher: str) -> tuple[bool, str | None]:
    """Checks a locally-used publisher string against GCD's real, normalized
    Publisher table (one canonical name per publisher - see gcd_models.py).
    Returns (is_exact_match, suggestion):
    - (True, None): local_publisher already matches a GCD publisher name
      case-insensitively - nothing to fix.
    - (False, name): no exact match, but exactly one GCD publisher name
      confidently looks like the same publisher (starts-with, e.g. "DC" ->
      "DC Comics"; falling back to contains if starts-with finds nothing) -
      a real candidate to suggest.
    - (False, None): no exact match and no single confident candidate -
      either nothing found, or multiple equally-plausible GCD publishers.
      Deliberately not guessing which one; the report still surfaces this
      row so it's visible, just without an auto-fillable suggestion."""
    stripped = local_publisher.strip()
    exact = gcd_db.query(Publisher).filter(func.lower(Publisher.name) == stripped.lower()).first()
    if exact:
        return True, None

    escaped = _escape_like(stripped)
    starts_with = gcd_db.query(Publisher.name).filter(Publisher.name.ilike(f"{escaped}%", escape="\\")).limit(6).all()
    if len(starts_with) == 1:
        return False, starts_with[0][0]

    contains = gcd_db.query(Publisher.name).filter(Publisher.name.ilike(f"%{escaped}%", escape="\\")).limit(6).all()
    if len(contains) == 1:
        return False, contains[0][0]

    return False, None


def get_publisher_mismatches(db: Session, gcd_db: Session) -> list[dict]:
    """Admin data-quality report (routes/admin.py) - every locally-used
    publisher string that doesn't exactly match GCD's canonical name for
    that publisher, with a confident suggestion where one exists. Read-only;
    the bulk-apply route does the actual merging via
    crud.bulk_merge_comic_field."""
    results = []
    for local_publisher, comic_count in get_distinct_publishers(db):
        is_exact, suggestion = suggest_gcd_publisher(gcd_db, local_publisher)
        if is_exact:
            continue
        results.append({
            "local_publisher": local_publisher,
            "comic_count": comic_count,
            "suggested_publisher": suggestion,
        })
    results.sort(key=lambda r: -r["comic_count"])
    return results
