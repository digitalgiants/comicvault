from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SeriesIndex(Base):
    """One row per coverbrowser series slug, from crawling /a-z/<bucket>.
    Rebuilt/refreshed by the `index` CLI command; `match` reads this rather
    than hitting coverbrowser live for every GCD series."""

    __tablename__ = "series_index"
    __table_args__ = (UniqueConstraint("slug", name="uq_series_index_slug"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(255), index=True)
    title_raw: Mapped[str] = mapped_column(String(255))
    normalized_title: Mapped[str] = mapped_column(String(255), index=True)
    # Covers, not strictly issues - coverbrowser's footnote count includes
    # variants/reprints, so this is a loose plausibility signal only.
    cover_count_hint: Mapped[int | None] = mapped_column(Integer, nullable=True)
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SeriesMatch(Base):
    """An accepted link from one GCD series to one coverbrowser slug. Never
    written directly for an ambiguous case - see SeriesMatchCandidate."""

    __tablename__ = "series_match"
    __table_args__ = (UniqueConstraint("gcd_series_id", name="uq_series_match_gcd_series"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    gcd_series_id: Mapped[int] = mapped_column(Integer, index=True)
    slug: Mapped[str] = mapped_column(String(255))
    # Which signals fired (see matcher.py) - kept for auditing, not logic.
    signals: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SeriesMatchCandidate(Base):
    """A GCD series that couldn't be linked automatically - either no
    candidate at all, or more than one and nothing to disambiguate them.
    Queued for a human to resolve rather than guessed; nothing in this
    service ever reads this table back into SeriesMatch automatically."""

    __tablename__ = "series_match_candidate"

    id: Mapped[int] = mapped_column(primary_key=True)
    gcd_series_id: Mapped[int] = mapped_column(Integer, index=True, unique=True)
    gcd_series_name: Mapped[str] = mapped_column(String(255))
    reason: Mapped[str] = mapped_column(String(40))  # "no_match" | "ambiguous" | "verification_failed"
    # [{slug, title_raw, cover_count_hint, score, reasons}, ...]
    candidates: Mapped[list] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | resolved | rejected
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
