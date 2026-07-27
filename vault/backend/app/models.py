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
