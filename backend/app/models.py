from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, JSON, String, Text
)
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user_comics = relationship("UserComic", back_populates="user")
    csv_imports = relationship("CSVImport", back_populates="user")
    comics_added = relationship("Comic", back_populates="created_by_user")


class Comic(Base):
    __tablename__ = "comics"

    id = Column(Integer, primary_key=True, index=True)
    upc = Column(String, unique=True, nullable=True, index=True)
    publisher = Column(String, index=True)
    name = Column(String, index=True, nullable=False)
    volume = Column(String, nullable=True)
    number = Column(String, nullable=True, index=True)
    print = Column(String, nullable=True)
    cover = Column(String, nullable=True)
    variant = Column(String, nullable=True)
    direct = Column(Boolean, nullable=True)
    writer = Column(String, nullable=True, index=True)
    artist = Column(String, nullable=True)
    pencils = Column(String, nullable=True)
    inker = Column(String, nullable=True)
    cover_artist = Column(String, nullable=True)
    average_price = Column(Float, nullable=True)
    print_ratio = Column(String, nullable=True)
    cover_image_url = Column(String, nullable=True)
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
    number_of_books = Column(Integer, default=1)
    price_paid = Column(Float, nullable=True)
    point_of_purchase = Column(String, nullable=True)
    buy_date = Column(DateTime, nullable=True)
    signed = Column(Boolean, default=False)
    remarked = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    sell_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="user_comics")
    comic = relationship("Comic", back_populates="user_comics")


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
