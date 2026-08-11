"""SQLAlchemy models for the curated subset of GCD's schema.

Table and column names match GCD's own SQLite dump (verified against a real
dump -- see README) so this stays directly recognizable against GCD's public
schema documentation. Only fields relevant to a comics catalog are kept;
bookkeeping columns (created/modified timestamps, *_uncertain flags, birth/
death biographical detail, etc.) are dropped as out of scope for the curated
subset.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Language(Base):
    __tablename__ = "stddata_language"

    id = Column(Integer, primary_key=True, autoincrement=False)
    code = Column(String(10), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    native_name = Column(String(255))


class Country(Base):
    __tablename__ = "stddata_country"

    id = Column(Integer, primary_key=True, autoincrement=False)
    code = Column(String(10), nullable=False, unique=True)
    name = Column(String(255), nullable=False)


class Publisher(Base):
    __tablename__ = "gcd_publisher"

    id = Column(Integer, primary_key=True, autoincrement=False)
    name = Column(String(255), nullable=False)
    country_id = Column(Integer, ForeignKey("stddata_country.id"), nullable=False)
    year_began = Column(Integer)
    year_ended = Column(Integer)
    notes = Column(Text, nullable=False, default="")
    url = Column(String(255), nullable=False, default="")


class IndiciaPublisher(Base):
    __tablename__ = "gcd_indicia_publisher"

    id = Column(Integer, primary_key=True, autoincrement=False)
    name = Column(String(255), nullable=False)
    parent_id = Column(Integer, ForeignKey("gcd_publisher.id"), nullable=False)
    country_id = Column(Integer, ForeignKey("stddata_country.id"), nullable=False)
    year_began = Column(Integer)
    year_ended = Column(Integer)
    is_surrogate = Column(Boolean, nullable=False, default=False)
    notes = Column(Text, nullable=False, default="")
    url = Column(String(255), nullable=False, default="")


class BrandGroup(Base):
    __tablename__ = "gcd_brand_group"

    id = Column(Integer, primary_key=True, autoincrement=False)
    name = Column(String(255), nullable=False)
    parent_id = Column(Integer, ForeignKey("gcd_publisher.id"), nullable=False)
    year_began = Column(Integer)
    year_ended = Column(Integer)
    notes = Column(Text, nullable=False, default="")
    url = Column(String(255), nullable=False, default="")


class Brand(Base):
    __tablename__ = "gcd_brand"

    id = Column(Integer, primary_key=True, autoincrement=False)
    name = Column(String(255), nullable=False)
    year_began = Column(Integer)
    year_ended = Column(Integer)
    notes = Column(Text, nullable=False, default="")
    url = Column(String(255), nullable=False, default="")
    generic = Column(Boolean, nullable=False, default=False)


class BrandEmblemGroup(Base):
    __tablename__ = "gcd_brand_emblem_group"

    id = Column(Integer, primary_key=True, autoincrement=False)
    brand_id = Column(Integer, ForeignKey("gcd_brand.id"), nullable=False)
    brandgroup_id = Column(Integer, ForeignKey("gcd_brand_group.id"), nullable=False)


class Series(Base):
    __tablename__ = "gcd_series"

    id = Column(Integer, primary_key=True, autoincrement=False)
    name = Column(String(255), nullable=False)
    sort_name = Column(String(255), nullable=False)
    format = Column(String(255), nullable=False, default="")
    year_began = Column(Integer, nullable=False)
    year_ended = Column(Integer)
    publication_dates = Column(String(255), nullable=False, default="")
    is_current = Column(Boolean, nullable=False, default=False)
    publisher_id = Column(Integer, ForeignKey("gcd_publisher.id"), nullable=False)
    country_id = Column(Integer, ForeignKey("stddata_country.id"), nullable=False)
    language_id = Column(Integer, ForeignKey("stddata_language.id"), nullable=False)
    notes = Column(Text, nullable=False, default="")
    issue_count = Column(Integer, nullable=False, default=0)
    is_comics_publication = Column(Boolean, nullable=False, default=True)


class Issue(Base):
    __tablename__ = "gcd_issue"

    id = Column(Integer, primary_key=True, autoincrement=False)
    number = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False, default="")
    volume = Column(String(50), nullable=False, default="")
    series_id = Column(Integer, ForeignKey("gcd_series.id"), nullable=False)
    indicia_publisher_id = Column(Integer, ForeignKey("gcd_indicia_publisher.id"))
    brand_id = Column(Integer, ForeignKey("gcd_brand.id"))
    variant_of_id = Column(Integer, ForeignKey("gcd_issue.id"))
    variant_name = Column(String(255), nullable=False, default="")
    isbn = Column(String(32), nullable=False, default="")
    barcode = Column(String(38), nullable=False, default="")
    publication_date = Column(String(255), nullable=False, default="")
    key_date = Column(String(10), nullable=False, default="")
    on_sale_date = Column(String(10), nullable=False, default="")
    sort_code = Column(Integer, nullable=False)
    price = Column(String(255), nullable=False, default="")
    page_count = Column(Numeric(10, 3))
    rating = Column(String(255), nullable=False, default="")
    editing = Column(Text, nullable=False, default="")
    notes = Column(Text, nullable=False, default="")


class StoryType(Base):
    __tablename__ = "gcd_story_type"

    id = Column(Integer, primary_key=True, autoincrement=False)
    name = Column(String(50), nullable=False, unique=True)
    sort_code = Column(Integer, nullable=False, unique=True)


class Story(Base):
    __tablename__ = "gcd_story"

    id = Column(Integer, primary_key=True, autoincrement=False)
    title = Column(String(255), nullable=False, default="")
    feature = Column(String(255), nullable=False, default="")
    sequence_number = Column(Integer, nullable=False)
    page_count = Column(Numeric(10, 3))
    issue_id = Column(Integer, ForeignKey("gcd_issue.id"), nullable=False)
    type_id = Column(Integer, ForeignKey("gcd_story_type.id"), nullable=False)
    job_number = Column(String(25), nullable=False, default="")
    genre = Column(String(255), nullable=False, default="")
    script = Column(Text, nullable=False, default="")
    pencils = Column(Text, nullable=False, default="")
    inks = Column(Text, nullable=False, default="")
    colors = Column(Text, nullable=False, default="")
    letters = Column(Text, nullable=False, default="")
    editing = Column(Text, nullable=False, default="")
    characters = Column(Text, nullable=False, default="")
    synopsis = Column(Text, nullable=False, default="")
    reprint_notes = Column(Text, nullable=False, default="")
    notes = Column(Text, nullable=False, default="")


class CreditType(Base):
    __tablename__ = "gcd_credit_type"

    id = Column(Integer, primary_key=True, autoincrement=False)
    name = Column(String(50), nullable=False, unique=True)
    sort_code = Column(Integer, nullable=False, unique=True)


class Creator(Base):
    __tablename__ = "gcd_creator"

    id = Column(Integer, primary_key=True, autoincrement=False)
    gcd_official_name = Column(String(255), nullable=False)
    sort_name = Column(String(255), nullable=False, default="")
    disambiguation = Column(String(255), nullable=False, default="")


class CreatorNameDetail(Base):
    __tablename__ = "gcd_creator_name_detail"

    id = Column(Integer, primary_key=True, autoincrement=False)
    name = Column(String(255), nullable=False)
    sort_name = Column(String(255), nullable=False, default="")
    is_official_name = Column(Boolean, nullable=False, default=False)
    creator_id = Column(Integer, ForeignKey("gcd_creator.id"), nullable=False)
    family_name = Column(String(255), nullable=False, default="")
    given_name = Column(String(255), nullable=False, default="")


class StoryCredit(Base):
    __tablename__ = "gcd_story_credit"

    id = Column(Integer, primary_key=True, autoincrement=False)
    story_id = Column(Integer, ForeignKey("gcd_story.id"), nullable=False)
    creator_id = Column(Integer, ForeignKey("gcd_creator_name_detail.id"), nullable=False)
    credit_type_id = Column(Integer, ForeignKey("gcd_credit_type.id"), nullable=False)
    credited_as = Column(String(255), nullable=False, default="")
    credit_name = Column(String(255), nullable=False, default="")
    is_credited = Column(Boolean, nullable=False, default=False)
    is_signed = Column(Boolean, nullable=False, default=False)
    uncertain = Column(Boolean, nullable=False, default=False)


# Load order matters for FK integrity on first insert.
LOAD_ORDER: list[type[Base]] = [
    Language,
    Country,
    Publisher,
    IndiciaPublisher,
    BrandGroup,
    Brand,
    BrandEmblemGroup,
    Series,
    Issue,
    StoryType,
    CreditType,
    Creator,
    CreatorNameDetail,
    Story,
    StoryCredit,
]
