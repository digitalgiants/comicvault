"""Extracts curated-subset rows out of a GCD SQLite dump as plain dicts,
scoped to the id sets a `filters.FilterResult` resolved.

Small lookup tables (languages, countries, story/credit types) are loaded in
full -- they're reference data, not something to filter.
"""

from __future__ import annotations

import sqlite3

from gcd_modifier import models
from gcd_modifier.filters import CHUNK_SIZE, FilterResult

# Column lists mirror models.py exactly -- keep the two in sync.
_COLUMNS: dict[str, list[str]] = {
    "stddata_language": ["id", "code", "name", "native_name"],
    "stddata_country": ["id", "code", "name"],
    "gcd_publisher": ["id", "name", "country_id", "year_began", "year_ended", "notes", "url"],
    "gcd_indicia_publisher": [
        "id",
        "name",
        "parent_id",
        "country_id",
        "year_began",
        "year_ended",
        "is_surrogate",
        "notes",
        "url",
    ],
    "gcd_brand_group": ["id", "name", "parent_id", "year_began", "year_ended", "notes", "url"],
    "gcd_brand": ["id", "name", "year_began", "year_ended", "notes", "url", "generic"],
    "gcd_brand_emblem_group": ["id", "brand_id", "brandgroup_id"],
    "gcd_series": [
        "id",
        "name",
        "sort_name",
        "format",
        "year_began",
        "year_ended",
        "publication_dates",
        "is_current",
        "publisher_id",
        "country_id",
        "language_id",
        "notes",
        "issue_count",
        "is_comics_publication",
    ],
    "gcd_issue": [
        "id",
        "number",
        "title",
        "volume",
        "series_id",
        "indicia_publisher_id",
        "brand_id",
        "variant_of_id",
        "variant_name",
        "isbn",
        "barcode",
        "publication_date",
        "key_date",
        "on_sale_date",
        "sort_code",
        "price",
        "page_count",
        "rating",
        "editing",
        "notes",
    ],
    "gcd_story_type": ["id", "name", "sort_code"],
    "gcd_credit_type": ["id", "name", "sort_code"],
    "gcd_creator": ["id", "gcd_official_name", "sort_name", "disambiguation"],
    "gcd_creator_name_detail": [
        "id",
        "name",
        "sort_name",
        "is_official_name",
        "creator_id",
        "family_name",
        "given_name",
    ],
    "gcd_story": [
        "id",
        "title",
        "feature",
        "sequence_number",
        "page_count",
        "issue_id",
        "type_id",
        "job_number",
        "genre",
        "script",
        "pencils",
        "inks",
        "colors",
        "letters",
        "editing",
        "characters",
        "synopsis",
        "reprint_notes",
        "notes",
    ],
    "gcd_story_credit": [
        "id",
        "story_id",
        "creator_id",
        "credit_type_id",
        "credited_as",
        "credit_name",
        "is_credited",
        "is_signed",
        "uncertain",
    ],
}


def _rows_for_ids(conn: sqlite3.Connection, table: str, ids: set[int]) -> list[dict]:
    columns = _COLUMNS[table]
    col_list = ", ".join(columns)
    ordered = list(ids)
    rows: list[dict] = []
    for i in range(0, len(ordered), CHUNK_SIZE):
        chunk = ordered[i : i + CHUNK_SIZE]
        placeholders = ",".join("?" * len(chunk))
        cursor = conn.execute(f"SELECT {col_list} FROM {table} WHERE id IN ({placeholders})", chunk)
        rows.extend(dict(zip(columns, row)) for row in cursor)
    return rows


def _all_rows(conn: sqlite3.Connection, table: str) -> list[dict]:
    columns = _COLUMNS[table]
    col_list = ", ".join(columns)
    cursor = conn.execute(f"SELECT {col_list} FROM {table}")
    return [dict(zip(columns, row)) for row in cursor]


def extract(conn: sqlite3.Connection, result: FilterResult) -> dict[str, list[dict]]:
    """Returns rows keyed by table name, in `models.LOAD_ORDER`'s dependency order."""
    return {
        "stddata_language": _all_rows(conn, "stddata_language"),
        "stddata_country": _all_rows(conn, "stddata_country"),
        "gcd_publisher": _rows_for_ids(conn, "gcd_publisher", result.publisher_ids),
        "gcd_indicia_publisher": _rows_for_ids(conn, "gcd_indicia_publisher", result.indicia_publisher_ids),
        "gcd_brand_group": _rows_for_ids(conn, "gcd_brand_group", result.brand_group_ids),
        "gcd_brand": _rows_for_ids(conn, "gcd_brand", result.brand_ids),
        "gcd_brand_emblem_group": [
            row
            for row in _all_rows(conn, "gcd_brand_emblem_group")
            if row["brand_id"] in result.brand_ids
        ],
        "gcd_series": _rows_for_ids(conn, "gcd_series", result.series_ids),
        "gcd_issue": _rows_for_ids(conn, "gcd_issue", result.issue_ids),
        "gcd_story_type": _all_rows(conn, "gcd_story_type"),
        "gcd_credit_type": _all_rows(conn, "gcd_credit_type"),
        "gcd_creator": _rows_for_ids(conn, "gcd_creator", result.creator_ids),
        "gcd_creator_name_detail": _rows_for_ids(conn, "gcd_creator_name_detail", result.creator_name_detail_ids),
        "gcd_story": _rows_for_ids(conn, "gcd_story", result.story_ids),
        "gcd_story_credit": _rows_for_ids(conn, "gcd_story_credit", result.story_credit_ids),
    }


assert {m.__tablename__ for m in models.LOAD_ORDER} == set(_COLUMNS), "transform._COLUMNS must match models.LOAD_ORDER"
