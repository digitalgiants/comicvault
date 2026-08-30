"""Read-only access to gcd-modifier's `gcd` database - only the two tables
and columns actually needed to build a matching candidate list. Deliberately
duplicated from vault/backend/app/gcd_models.py rather than shared, matching
this repo's existing convention of keeping each service's models independent.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Session


class GcdReadBase(DeclarativeBase):
    pass


class Publisher(GcdReadBase):
    __tablename__ = "gcd_publisher"

    id = Column(Integer, primary_key=True, autoincrement=False)
    name = Column(String(255), nullable=False)


class Series(GcdReadBase):
    __tablename__ = "gcd_series"

    id = Column(Integer, primary_key=True, autoincrement=False)
    name = Column(String(255), nullable=False)
    year_began = Column(Integer, nullable=False)
    year_ended = Column(Integer)
    publisher_id = Column(Integer, ForeignKey("gcd_publisher.id"), nullable=False)
    issue_count = Column(Integer, nullable=False, default=0)


@dataclass
class GcdSeriesSummary:
    id: int
    name: str
    publisher_name: str | None
    year_began: int
    year_ended: int | None
    issue_count: int


def get_series_before(gcd_db: Session, cutoff_year: int) -> list[GcdSeriesSummary]:
    """Series in scope for the coverbrowser matcher. Limited to series that
    *began* before `cutoff_year` (default 2011 - see matcher.py's module
    docstring for why): coverbrowser's own coverage appears to stop around
    the 2011-era relaunch wave for most flagship titles, so anything newer
    is unlikely to have a match at all and isn't worth the request budget to
    check."""
    rows = (
        gcd_db.query(Series, Publisher.name)
        .outerjoin(Publisher, Series.publisher_id == Publisher.id)
        .filter(Series.year_began < cutoff_year)
        .all()
    )
    return [
        GcdSeriesSummary(
            id=series.id,
            name=series.name,
            publisher_name=publisher_name,
            year_began=series.year_began,
            year_ended=series.year_ended,
            issue_count=series.issue_count,
        )
        for series, publisher_name in rows
    ]
