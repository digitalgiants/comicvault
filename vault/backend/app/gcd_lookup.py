"""GCD-first comic lookup: barcode matching and series/issue search against
the local `gcd` database (see app.gcd_database / app.gcd_models). Callers
(routes/scan.py, routes/search.py) treat a None/empty result the same as a
cache miss and fall through to the existing Metron/ComicVine lookup path.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Iterable

from sqlalchemy.orm import Session

from app.crud import normalize_issue_number, normalize_search_query
from app.gcd_models import Issue, Publisher, Series, Story, StoryType
from app.schemas import ComicCreate, ExternalIssueSummary, ExternalSeriesResult

SEARCH_LIMIT = 20
COMIC_STORY_TYPE = "comic story"

_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_USD_PRICE_RE = re.compile(r"(\d+\.\d{2})\s*USD", re.IGNORECASE)
_ANY_PRICE_RE = re.compile(r"(\d+\.\d{2})")


def find_issue_by_upc(gcd_db: Session, upc12: str) -> Issue | None:
    """Matches gcd_issue.barcode against a scanned 12-digit UPC.

    GCD's barcode field stores either a bare 12-digit UPC, or UPC + 5-digit
    price supplement concatenated (17 digits total) - either way the UPC is
    the leading 12 digits, so a prefix match covers both. ISBN-based barcodes
    (18 digits, "978..." prefix) are intentionally excluded - a scanned code
    is never 13 digits, so they'd never match a 12-digit prefix anyway.

    Multiple matches (e.g. shared UPCs across variant printings) prefer an
    exact-length match over a prefix match, else the lowest id, rather than
    treating it as ambiguous - GCD is meant to be authoritative here.
    """
    candidates = gcd_db.query(Issue).filter(Issue.barcode.like(f"{upc12}%")).all()
    if not candidates:
        return None
    for issue in candidates:
        if issue.barcode == upc12:
            return issue
    return min(candidates, key=lambda i: i.id)


def search_series(gcd_db: Session, query: str, limit: int = SEARCH_LIMIT) -> list[ExternalSeriesResult]:
    normalized = normalize_search_query(query)
    if not normalized:
        return []
    rows = (
        gcd_db.query(Series, Publisher)
        .join(Publisher, Series.publisher_id == Publisher.id)
        .filter(Series.name.ilike(f"%{normalized}%"))
        .order_by(Series.name)
        .limit(limit)
        .all()
    )
    return [
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


def get_series_issues(gcd_db: Session, series_id: int, number: str | None = None) -> list[ExternalIssueSummary]:
    issues = gcd_db.query(Issue).filter(Issue.series_id == series_id).all()
    if number:
        target = normalize_issue_number(number)
        issues = [i for i in issues if normalize_issue_number(i.number) == target]
    return [
        ExternalIssueSummary(
            provider="gcd",
            provider_issue_id=str(issue.id),
            number=issue.number or None,
            cover_date=issue.key_date or None,
            image=None,
        )
        for issue in issues
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

    return ComicCreate(
        publisher=publisher.name,
        series=series.name,
        volume=issue.volume or None,
        issue_number=issue.number or None,
        legacy_number=None,
        cover_date=_parse_gcd_date(issue.key_date),
        store_date=_parse_gcd_date(issue.on_sale_date),
        print_run=None,
        variant=(issue.variant_name or None) if issue.variant_of_id else None,
        direct=None,
        writer=writer,
        penciller=penciller,
        inker=inker,
        cover_artist=None,
        average_price=_parse_gcd_price(issue.price),
        upc=None,
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
