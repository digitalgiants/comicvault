from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from sqlalchemy import URL, Boolean, bindparam, create_engine, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from gcd_modifier import models, transform
from gcd_modifier.filters import resolve

logger = logging.getLogger(__name__)

UPSERT_BATCH_SIZE = 1000


def load_dump(sqlite_path: Path, database_url: URL) -> None:
    conn = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    try:
        logger.info("Resolving English-language comics series and their dependents...")
        filter_result = resolve(conn)
        logger.info("%d series matched", len(filter_result.series_ids))

        logger.info("Extracting curated rows from %s...", sqlite_path)
        rows_by_table = transform.extract(conn, filter_result)
    finally:
        conn.close()

    _sanitize_fk_integrity(rows_by_table)
    _coerce_booleans(rows_by_table)

    engine = create_engine(database_url)
    models.Base.metadata.create_all(engine)

    with Session(engine) as session:
        for model in models.LOAD_ORDER:
            rows = rows_by_table[model.__tablename__]
            _upsert(session, model, rows)
            session.commit()
            logger.info("Loaded %d rows into %s", len(rows), model.__tablename__)


def _sanitize_fk_integrity(rows_by_table: dict[str, list[dict]]) -> None:
    """Repairs dangling foreign keys before they hit Postgres's FK constraints.

    GCD's own dump isn't perfectly self-consistent -- a handful of rows
    reference parent rows (brands, brand groups, creator name details) that
    don't actually exist in the dump. Nullable FK columns get nulled out;
    rows with a required FK pointing nowhere are dropped. Processed in
    `models.LOAD_ORDER` so every parent table's final id set is known before
    its children are checked against it (self-referencing FKs, e.g.
    `gcd_issue.variant_of_id`, are checked against the table's own ids).
    """
    loaded_ids: dict[str, set[int]] = {}

    for model in models.LOAD_ORDER:
        table = model.__table__
        rows = rows_by_table[table.name]
        own_ids = {row["id"] for row in rows}

        fk_columns = [
            (fk.parent.name, fk.column.table.name, fk.parent.nullable) for fk in table.foreign_keys
        ]

        if fk_columns:
            kept = []
            dropped = 0
            for row in rows:
                valid = True
                for col_name, parent_table, nullable in fk_columns:
                    value = row.get(col_name)
                    if value is None:
                        continue
                    parent_ids = own_ids if parent_table == table.name else loaded_ids[parent_table]
                    if value not in parent_ids:
                        if nullable:
                            row[col_name] = None
                        else:
                            valid = False
                            break
                if valid:
                    kept.append(row)
                else:
                    dropped += 1
            if dropped:
                logger.warning(
                    "Dropped %d %s row(s) referencing missing parent rows (GCD dump data-quality gap)",
                    dropped,
                    table.name,
                )
            rows_by_table[table.name] = kept
            own_ids = {row["id"] for row in kept}

        loaded_ids[table.name] = own_ids


def _coerce_booleans(rows_by_table: dict[str, list[dict]]) -> None:
    """SQLite has no native boolean type -- these come back as plain 0/1 ints,
    which isn't guaranteed to bind cleanly against a Postgres `boolean` column
    depending on driver version. Coerce explicitly rather than rely on that.
    """
    for model in models.LOAD_ORDER:
        table = model.__table__
        bool_columns = [c.name for c in table.columns if isinstance(c.type, Boolean)]
        if not bool_columns:
            continue
        for row in rows_by_table[table.name]:
            for col in bool_columns:
                if row.get(col) is not None:
                    row[col] = bool(row[col])


def _upsert(session: Session, model: type[models.Base], rows: list[dict]) -> None:
    if not rows:
        return

    table = model.__table__
    # Self-referencing FKs (e.g. gcd_issue.variant_of_id -> gcd_issue.id) can
    # point to a row that hasn't been inserted yet, since rows are chunked
    # into batches in no particular dependency order -- Postgres checks the
    # FK immediately per-statement, not at end-of-transaction, so that batch
    # would fail. Load with those columns nulled first, then a second pass
    # fills them in once every row in the table is guaranteed to exist.
    self_ref_columns = [fk.parent.name for fk in table.foreign_keys if fk.column.table.name == table.name]

    deferred: list[dict] = []
    if self_ref_columns:
        rows = [dict(row) for row in rows]
        for row in rows:
            values = {col: row[col] for col in self_ref_columns if row.get(col) is not None}
            if values:
                deferred.append({"_id": row["id"], **values})
                for col in self_ref_columns:
                    row[col] = None

    update_columns = [c.name for c in table.columns if c.name != "id"]

    for i in range(0, len(rows), UPSERT_BATCH_SIZE):
        batch = rows[i : i + UPSERT_BATCH_SIZE]
        stmt = pg_insert(table).values(batch)
        if update_columns:
            stmt = stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={col: getattr(stmt.excluded, col) for col in update_columns},
            )
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=["id"])
        session.execute(stmt)

    if deferred:
        stmt = (
            update(table)
            .where(table.c.id == bindparam("_id"))
            .values({col: bindparam(col) for col in self_ref_columns})
        )
        for i in range(0, len(deferred), UPSERT_BATCH_SIZE):
            session.execute(stmt, deferred[i : i + UPSERT_BATCH_SIZE])
