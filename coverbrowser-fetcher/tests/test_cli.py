from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from coverbrowser_fetcher import models
from coverbrowser_fetcher.cli import _persist_result, _upsert_index_entries
from coverbrowser_fetcher.crawler import IndexEntry
from coverbrowser_fetcher.matcher import MatchCandidate, MatchResult


def make_db():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_upsert_index_entries_is_idempotent_by_slug():
    db = make_db()
    _upsert_index_entries(db, [IndexEntry(slug="badger", title_raw="Badger", cover_count_hint=70)])
    db.commit()
    # Re-crawling the same page later with an updated count should update
    # the existing row, not create a duplicate.
    _upsert_index_entries(db, [IndexEntry(slug="badger", title_raw="Badger", cover_count_hint=71)])
    db.commit()

    rows = db.query(models.SeriesIndex).all()
    assert len(rows) == 1
    assert rows[0].cover_count_hint == 71


def test_persist_result_auto_writes_series_match():
    db = make_db()
    accepted = MatchCandidate(slug="badger", title_raw="Badger", cover_count_hint=70, score=1.5, reasons=["exact_title_match", "plausible_cover_count"])
    result = MatchResult(gcd_series_id=42, gcd_series_name="Badger", status="auto", accepted=accepted, candidates=[accepted], reason="unique_match")

    _persist_result(db, result)
    db.commit()

    match = db.query(models.SeriesMatch).filter_by(gcd_series_id=42).one()
    assert match.slug == "badger"
    assert db.query(models.SeriesMatchCandidate).count() == 0


def test_persist_result_review_writes_series_match_candidate_not_series_match():
    db = make_db()
    candidates = [
        MatchCandidate(slug="badger", title_raw="Badger", cover_count_hint=70, score=1.0, reasons=["exact_title_match"]),
        MatchCandidate(slug="badger-reprint", title_raw="Badger", cover_count_hint=12, score=1.0, reasons=["exact_title_match"]),
    ]
    result = MatchResult(gcd_series_id=42, gcd_series_name="Badger", status="review", accepted=None, candidates=candidates, reason="ambiguous")

    _persist_result(db, result)
    db.commit()

    assert db.query(models.SeriesMatch).count() == 0
    candidate_row = db.query(models.SeriesMatchCandidate).filter_by(gcd_series_id=42).one()
    assert candidate_row.reason == "ambiguous"
    assert len(candidate_row.candidates) == 2
    assert candidate_row.status == "pending"
