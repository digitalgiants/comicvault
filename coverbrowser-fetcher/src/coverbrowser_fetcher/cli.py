from __future__ import annotations

import logging
from datetime import datetime, timezone

import typer
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, sessionmaker

from coverbrowser_fetcher import crawler, gcd_read, matcher, models
from coverbrowser_fetcher.config import get_settings
from coverbrowser_fetcher.crawler import INDEX_BUCKETS, CoverbrowserBlocked, ThrottledClient
from coverbrowser_fetcher.normalize import normalize_title

app = typer.Typer()
logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@app.command()
def index() -> None:
    """Crawl coverbrowser's 27 /a-z/<bucket> pages once and (re)populate the
    local series_index table. Safe to re-run - upserts by slug. Does not
    touch GCD or do any matching."""
    _configure_logging()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    models.Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    with ThrottledClient(settings.user_agent, settings.request_delay_seconds) as client, session_factory() as db:
        for bucket in INDEX_BUCKETS:
            try:
                entries = crawler.fetch_index_bucket(client, bucket)
            except CoverbrowserBlocked as exc:
                logger.error("Stopping: %s", exc)
                raise typer.Exit(code=1) from exc
            logger.info("bucket %r: %d series", bucket, len(entries))
            _upsert_index_entries(db, entries)
            db.commit()


def _upsert_index_entries(db: Session, entries: list[crawler.IndexEntry]) -> None:
    now = datetime.now(timezone.utc)
    for entry in entries:
        values = {
            "slug": entry.slug,
            "title_raw": entry.title_raw,
            "normalized_title": normalize_title(entry.title_raw),
            "cover_count_hint": entry.cover_count_hint,
            "indexed_at": now,
        }
        stmt = pg_insert(models.SeriesIndex).values(**values)
        stmt = stmt.on_conflict_do_update(index_elements=["slug"], set_=values)
        db.execute(stmt)


@app.command()
def match(
    cutoff_year: int = typer.Option(2011, help="Only consider GCD series with year_began before this year"),
    limit: int = typer.Option(0, help="Stop after this many series (0 = no limit) - use to test in small batches"),
) -> None:
    """Match GCD series (pre-cutoff, unresolved) against the local
    series_index, writing confident links to series_match and everything
    else to series_match_candidate for manual review. Does not download any
    images - see the module docstrings in matcher.py/crawler.py for why."""
    _configure_logging()
    settings = get_settings()
    if not settings.gcd_database_url:
        raise typer.BadParameter("GCD_DATABASE_URL is not configured")

    engine = create_engine(settings.database_url)
    models.Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    gcd_session_factory = sessionmaker(bind=create_engine(settings.gcd_database_url))

    with (
        ThrottledClient(settings.user_agent, settings.request_delay_seconds) as client,
        session_factory() as db,
        gcd_session_factory() as gcd_db,
    ):
        index_by_title = matcher.build_index_by_title(
            [
                crawler.IndexEntry(slug=row.slug, title_raw=row.title_raw, cover_count_hint=row.cover_count_hint)
                for row in db.query(models.SeriesIndex).all()
            ]
        )
        logger.info("%d slugs loaded from local series_index", sum(len(v) for v in index_by_title.values()))

        series_list = gcd_read.get_series_before(gcd_db, cutoff_year)
        already_done = {
            row[0]
            for row in db.query(models.SeriesMatch.gcd_series_id).union(
                db.query(models.SeriesMatchCandidate.gcd_series_id)
            )
        }
        pending = [s for s in series_list if s.id not in already_done]
        logger.info("%d series before %d, %d already resolved, %d to check", len(series_list), cutoff_year, len(already_done), len(pending))

        checked = 0
        for series in pending:
            if limit and checked >= limit:
                logger.info("Reached limit=%d, stopping", limit)
                break

            candidates = matcher.find_candidates(series, index_by_title)
            result = matcher.decide(series, candidates)

            if result.status == "auto":
                try:
                    verified = crawler.verify_first_issue_present(client, result.accepted.slug)
                except CoverbrowserBlocked as exc:
                    logger.error("Stopping: %s", exc)
                    raise typer.Exit(code=1) from exc
                checked += 1
                if not verified:
                    logger.info("series %r (%d): candidate %r failed verification, queuing for review", series.name, series.id, result.accepted.slug)
                    result = matcher.MatchResult(series.id, series.name, "review", None, candidates, "verification_failed")

            _persist_result(db, result)
            db.commit()

        logger.info("Done - %d live verification fetches made", checked)


def _persist_result(db: Session, result: matcher.MatchResult) -> None:
    now = datetime.now(timezone.utc)
    if result.status == "auto":
        db.add(
            models.SeriesMatch(
                gcd_series_id=result.gcd_series_id,
                slug=result.accepted.slug,
                signals=result.accepted.reasons,
                created_at=now,
            )
        )
        logger.info("MATCHED series %r (%d) -> /covers/%s", result.gcd_series_name, result.gcd_series_id, result.accepted.slug)
    else:
        db.add(
            models.SeriesMatchCandidate(
                gcd_series_id=result.gcd_series_id,
                gcd_series_name=result.gcd_series_name,
                reason=result.reason,
                candidates=[
                    {"slug": c.slug, "title_raw": c.title_raw, "cover_count_hint": c.cover_count_hint, "score": c.score, "reasons": c.reasons}
                    for c in result.candidates
                ],
                created_at=now,
            )
        )
        logger.info("QUEUED series %r (%d): %s (%d candidates)", result.gcd_series_name, result.gcd_series_id, result.reason, len(result.candidates))
