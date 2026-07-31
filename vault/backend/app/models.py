from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, JSON, String, Text, UniqueConstraint, Date
)
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    is_kiosk = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user_comics = relationship("UserComic", back_populates="user")
    csv_imports = relationship("CSVImport", back_populates="user")
    comics_added = relationship("Comic", back_populates="created_by_user")
    column_preferences = relationship("UserColumnPreference", back_populates="user")
    snapshots = relationship("CollectionSnapshot", back_populates="user")
    bug_reports = relationship("BugReport", back_populates="user")


class Comic(Base):
    __tablename__ = "comics"

    id = Column(Integer, primary_key=True, index=True)
    upc = Column(String, unique=True, nullable=True, index=True)
    img = Column(String, nullable=True)
    # Resolved from owners' personal photos (see crud.recompute_comic_master_photo)
    # - takes priority over img wherever the comic's cover is displayed, without
    # discarding the original looked-up image if the photo is later removed.
    master_photo = Column(String, nullable=True)
    publisher = Column(String, index=True)
    series = Column(String, index=True, nullable=False)
    volume = Column(String, nullable=True)
    issue_number = Column(String, nullable=True, index=True)
    cover_date = Column(Date, nullable=True)
    store_date = Column(Date, nullable=True)
    direct = Column(Boolean, nullable=True)
    print_run = Column(String, nullable=True)
    variant = Column(String, nullable=True)
    cover_artist = Column(String, nullable=True)
    artist = Column(String, nullable=True)
    penciller = Column(String, nullable=True)
    inker = Column(String, nullable=True)
    writer = Column(String, nullable=True, index=True)
    average_price = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_by_user = relationship("User", back_populates="comics_added")
    user_comics = relationship("UserComic", back_populates="comic")


class UserComic(Base):
    __tablename__ = "user_comics"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    comic_id = Column(Integer, ForeignKey("comics.id"), nullable=False, index=True)
    count = Column(Integer, default=1)
    paid_price = Column(Float, nullable=True)
    asking_price = Column(Float, nullable=True)
    point_of_purchase = Column(String, nullable=True)
    buy_date = Column(DateTime, nullable=True)
    signed = Column(Boolean, default=False)
    remarked = Column(Boolean, default=False)
    condition = Column(String, nullable=True)
    personal_img = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="user_comics")
    comic = relationship("Comic", back_populates="user_comics")
    sales = relationship("Sale", back_populates="user_comic", cascade="all, delete-orphan", order_by="Sale.sell_date")


class Sale(Base):
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, index=True)
    user_comic_id = Column(Integer, ForeignKey("user_comics.id"), nullable=False, index=True)
    sell_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    sell_price = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user_comic = relationship("UserComic", back_populates="sales")


class CSVImport(Base):
    __tablename__ = "csv_imports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    total_rows = Column(Integer, default=0)
    successful_imports = Column(Integer, default=0)
    failed_rows = Column(Integer, default=0)
    error_log = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="csv_imports")


class CollectionSnapshot(Base):
    __tablename__ = "collection_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    comic_count = Column(Integer, default=0)
    total_paid = Column(Float, default=0.0)
    total_value = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="snapshots")


class UserColumnPreference(Base):
    __tablename__ = "user_column_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    page = Column(String, nullable=False)  # 'collection' or 'sold'
    columns = Column(JSON, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "page", name="uq_user_page_prefs"),)

    user = relationship("User", back_populates="column_preferences")


class BugReport(Base):
    __tablename__ = "bug_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    text = Column(Text, nullable=False)
    comic_id = Column(Integer, ForeignKey("comics.id"), nullable=True)
    page_url = Column(String, nullable=True)
    resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="bug_reports")
    comic = relationship("Comic")


class KioskSignup(Base):
    __tablename__ = "kiosk_signups"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, nullable=False, index=True)
    phone = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class KioskFeaturedSet(Base):
    """Cached random selection for a kiosk section, regenerated once every 24h."""
    __tablename__ = "kiosk_featured_sets"

    section = Column(String, primary_key=True)
    item_ids = Column(JSON, default=list)
    generated_at = Column(DateTime, default=datetime.utcnow)


class ExternalSeriesSync(Base):
    """Tracks whether a provider's full issue list has been paginated into
    ExternalIssueCache, so repeat visits to a series don't re-hit the
    rate-limited external API."""
    __tablename__ = "external_series_syncs"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, nullable=False, index=True)
    provider_series_id = Column(String, nullable=False, index=True)
    series_name = Column(String, nullable=True)
    known_issue_count = Column(Integer, nullable=True)
    synced_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("provider", "provider_series_id", name="uq_series_sync_provider_id"),
    )


class ExternalIssueCache(Base):
    """Permanent local mirror of an external provider's issue data. Summary
    fields (number/cover_date/image) are populated when a series is paginated;
    detail fields are populated lazily the first time a specific issue's full
    fields are fetched for adding to a collection."""
    __tablename__ = "external_issue_cache"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, nullable=False, index=True)
    provider_issue_id = Column(String, nullable=False, index=True)
    # Nullable: a row created purely from an issue-fields lookup (rather than
    # from paginating its series) may not have this on hand.
    provider_series_id = Column(String, nullable=True, index=True)

    number = Column(String, nullable=True)
    cover_date = Column(String, nullable=True)
    image = Column(String, nullable=True)

    fields_synced = Column(Boolean, default=False)
    publisher = Column(String, nullable=True)
    series = Column(String, nullable=True)
    volume = Column(String, nullable=True)
    store_date = Column(String, nullable=True)
    print_run = Column(String, nullable=True)
    variant = Column(String, nullable=True)
    direct = Column(Boolean, nullable=True)
    writer = Column(String, nullable=True)
    artist = Column(String, nullable=True)
    penciller = Column(String, nullable=True)
    inker = Column(String, nullable=True)
    cover_artist = Column(String, nullable=True)
    average_price = Column(Float, nullable=True)
    upc = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("provider", "provider_issue_id", name="uq_issue_cache_provider_id"),
    )


class ExternalSeriesSearchLog(Base):
    """Tracks when a (provider, normalized query) title search was last run,
    so repeat searches serve from ExternalSeriesSearchCache instead of
    re-hitting the provider. Unlike issue data, series search results are
    given a TTL (not permanent) - new series get published/indexed over time,
    and there's no cheap way to detect that the way there is for issue
    counts on an already-known series."""
    __tablename__ = "external_series_search_logs"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, nullable=False, index=True)
    query = Column(String, nullable=False, index=True)
    searched_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("provider", "query", name="uq_series_search_log_provider_query"),
    )


class ExternalSeriesSearchCache(Base):
    """Cached results of a series-title search, keyed by normalized query text."""
    __tablename__ = "external_series_search_cache"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, nullable=False, index=True)
    query = Column(String, nullable=False, index=True)
    provider_series_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    publisher = Column(String, nullable=True)
    start_year = Column(Integer, nullable=True)
    issue_count = Column(Integer, nullable=True)
    image = Column(String, nullable=True)
