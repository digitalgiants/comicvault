"""Read-only SQLAlchemy models for the subset of gcd-modifier's schema this
app actually queries (lookup only - nothing here is ever written to).

Deliberately duplicated from gcd-modifier/src/gcd_modifier/models.py rather
than shared, matching this repo's existing convention of keeping services'
models independent (see Comics vs. Cards in this same backend). Only the
tables lookups actually need are modeled - gcd-modifier's own models.py has
the full curated set (credits, creators, brands, etc.) for loading purposes.
"""

from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base

GcdBase = declarative_base()


class Publisher(GcdBase):
    __tablename__ = "gcd_publisher"

    id = Column(Integer, primary_key=True, autoincrement=False)
    name = Column(String(255), nullable=False)


class Series(GcdBase):
    __tablename__ = "gcd_series"

    id = Column(Integer, primary_key=True, autoincrement=False)
    name = Column(String(255), nullable=False)
    year_began = Column(Integer, nullable=False)
    year_ended = Column(Integer)
    publisher_id = Column(Integer, ForeignKey("gcd_publisher.id"), nullable=False)
    issue_count = Column(Integer, nullable=False, default=0)


class Issue(GcdBase):
    __tablename__ = "gcd_issue"

    id = Column(Integer, primary_key=True, autoincrement=False)
    number = Column(String(50), nullable=False)
    volume = Column(String(50), nullable=False, default="")
    series_id = Column(Integer, ForeignKey("gcd_series.id"), nullable=False)
    variant_of_id = Column(Integer, ForeignKey("gcd_issue.id"))
    variant_name = Column(String(255), nullable=False, default="")
    barcode = Column(String(38), nullable=False, default="")
    key_date = Column(String(10), nullable=False, default="")
    on_sale_date = Column(String(10), nullable=False, default="")
    price = Column(String(255), nullable=False, default="")


class StoryType(GcdBase):
    __tablename__ = "gcd_story_type"

    id = Column(Integer, primary_key=True, autoincrement=False)
    name = Column(String(50), nullable=False, unique=True)


class Story(GcdBase):
    __tablename__ = "gcd_story"

    id = Column(Integer, primary_key=True, autoincrement=False)
    sequence_number = Column(Integer, nullable=False)
    issue_id = Column(Integer, ForeignKey("gcd_issue.id"), nullable=False)
    type_id = Column(Integer, ForeignKey("gcd_story_type.id"), nullable=False)
    script = Column(Text, nullable=False, default="")
    pencils = Column(Text, nullable=False, default="")
    inks = Column(Text, nullable=False, default="")
