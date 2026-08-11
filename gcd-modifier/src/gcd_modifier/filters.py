"""Resolves which rows belong in the curated, English-language-comics-only subset.

Everything cascades from `series`: a series qualifies if its language is
English, it's flagged as an actual comics publication (not a fanzine/other
non-comics GCD entry), and it isn't soft-deleted. Every other table's
inclusion is derived from that starting set of series ids.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

# SQLite's default SQLITE_MAX_VARIABLE_NUMBER is as low as 999 depending on
# how libsqlite3 was built (e.g. many Debian/Linux packages) -- id sets here
# can run into the hundreds of thousands, so every IN (...) lookup is chunked
# well under that floor rather than relying on the host's actual limit.
CHUNK_SIZE = 500


@dataclass
class FilterResult:
    series_ids: set[int] = field(default_factory=set)
    issue_ids: set[int] = field(default_factory=set)
    story_ids: set[int] = field(default_factory=set)
    story_credit_ids: set[int] = field(default_factory=set)
    publisher_ids: set[int] = field(default_factory=set)
    indicia_publisher_ids: set[int] = field(default_factory=set)
    brand_ids: set[int] = field(default_factory=set)
    brand_group_ids: set[int] = field(default_factory=set)
    creator_name_detail_ids: set[int] = field(default_factory=set)
    creator_ids: set[int] = field(default_factory=set)


def _chunks(ids: set[int]) -> list[tuple[int, ...]]:
    ordered = list(ids)
    return [tuple(ordered[i : i + CHUNK_SIZE]) for i in range(0, len(ordered), CHUNK_SIZE)]


def _lookup(
    conn: sqlite3.Connection,
    table: str,
    select_col: str,
    where_col: str,
    ids: set[int],
    exclude_deleted: bool = False,
) -> set[int]:
    """Returns the distinct values of `select_col` for rows where `where_col IN (ids)`.

    Deliberately never puts `deleted = 0` in the WHERE clause even when
    `exclude_deleted` is set: SQLite's planner will happily pick a
    low-selectivity index on `deleted` (almost every row has deleted=0) over
    a far better index on `where_col`, turning an indexed lookup into a
    near-full-table-scan per chunk. `deleted` is selected alongside the
    target column and filtered out here in Python instead, so the WHERE
    clause only ever contains the IN-list SQLite should actually index on.
    """
    cols = f"{select_col}, deleted" if exclude_deleted else select_col
    result: set[int] = set()
    for chunk in _chunks(ids):
        placeholders = ",".join("?" * len(chunk))
        rows = conn.execute(f"SELECT {cols} FROM {table} WHERE {where_col} IN ({placeholders})", chunk)
        if exclude_deleted:
            result |= {row[0] for row in rows if row[1] == 0 and row[0] is not None}
        else:
            result |= {row[0] for row in rows if row[0] is not None}
    return result


def resolve(conn: sqlite3.Connection) -> FilterResult:
    result = FilterResult()

    result.series_ids = {
        row[0]
        for row in conn.execute(
            """
            SELECT s.id FROM gcd_series s
            JOIN stddata_language l ON s.language_id = l.id
            WHERE l.code = 'en' AND s.is_comics_publication = 1 AND s.deleted = 0
            """
        )
    }
    if not result.series_ids:
        return result

    result.issue_ids = _lookup(conn, "gcd_issue", "id", "series_id", result.series_ids, exclude_deleted=True)
    result.story_ids = _lookup(conn, "gcd_story", "id", "issue_id", result.issue_ids, exclude_deleted=True)
    result.story_credit_ids = _lookup(
        conn, "gcd_story_credit", "id", "story_id", result.story_ids, exclude_deleted=True
    )

    result.publisher_ids = _lookup(conn, "gcd_series", "publisher_id", "id", result.series_ids)
    result.indicia_publisher_ids = _lookup(conn, "gcd_issue", "indicia_publisher_id", "id", result.issue_ids)
    result.brand_ids = _lookup(conn, "gcd_issue", "brand_id", "id", result.issue_ids)

    if result.indicia_publisher_ids:
        result.publisher_ids |= _lookup(
            conn, "gcd_indicia_publisher", "parent_id", "id", result.indicia_publisher_ids
        )

    if result.brand_ids:
        result.brand_group_ids = _lookup(
            conn, "gcd_brand_emblem_group", "brandgroup_id", "brand_id", result.brand_ids
        )

    if result.brand_group_ids:
        result.publisher_ids |= _lookup(conn, "gcd_brand_group", "parent_id", "id", result.brand_group_ids)

    result.creator_name_detail_ids = _lookup(
        conn, "gcd_story_credit", "creator_id", "id", result.story_credit_ids
    )
    result.creator_ids = _lookup(
        conn, "gcd_creator_name_detail", "creator_id", "id", result.creator_name_detail_ids
    )

    return result
