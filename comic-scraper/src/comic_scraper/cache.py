from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, URL, DateTime, String, UniqueConstraint, create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    pass


class LookupRecord(Base):
    __tablename__ = "lookups"
    __table_args__ = (UniqueConstraint("upc12", "ean5", name="uq_upc12_ean5"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    upc12: Mapped[str] = mapped_column(String(20), index=True)
    ean5: Mapped[str | None] = mapped_column(String(10), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LookupCache:
    def __init__(self, database_url: str | URL):
        self._engine = create_engine(database_url)
        Base.metadata.create_all(self._engine)

    def get(self, upc12: str, ean5: str | None) -> dict | None:
        with Session(self._engine) as session:
            stmt = select(LookupRecord).where(
                LookupRecord.upc12 == upc12, LookupRecord.ean5 == ean5
            )
            record = session.scalar(stmt)
            return record.payload if record else None

    def set(self, upc12: str, ean5: str | None, payload: dict) -> None:
        with Session(self._engine) as session:
            stmt = select(LookupRecord).where(
                LookupRecord.upc12 == upc12, LookupRecord.ean5 == ean5
            )
            record = session.scalar(stmt)
            if record is None:
                record = LookupRecord(upc12=upc12, ean5=ean5)
                session.add(record)
            record.payload = payload
            record.resolved_at = datetime.now(timezone.utc)
            try:
                session.commit()
            except IntegrityError:
                # Another thread in the same concurrent batch (see api.py's
                # ThreadPoolExecutor) raced this exact upc12+ean5 pair and
                # committed first - its payload is equally valid (same
                # real-world issue), so there's nothing left to do here.
                session.rollback()
