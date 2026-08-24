import csv
import io
from datetime import datetime
from typing import Any

import pandas as pd

REQUIRED_COLUMNS = {"series", "issuenumber"}

BOOLEAN_FIELDS = {"newstand", "signed", "remarked", "donotsell"}
FLOAT_FIELDS = {"paidprice", "averageprice", "sellprice", "askingprice"}
INT_FIELDS = {"count", "reservecount"}
DATE_FIELDS = {"buydate", "coverdate", "storedate", "selldate"}

COLUMN_MAP = {
    "upc": "upc",
    "img": "img",
    "series": "series",
    "volume": "volume",
    "issuenumber": "issue_number",
    "legacynumber": "legacy_number",
    "coverdate": "cover_date",
    "storedate": "store_date",
    "newstand": "newstand",
    "publisher": "publisher",
    "count": "count",
    "printrun": "print_run",
    "variant": "variant",
    "coverletter": "cover_letter",
    "coverartist": "cover_artist",
    "penciller": "penciller",
    "inker": "inker",
    "writer": "writer",
    "averageprice": "average_price",
    "paidprice": "paid_price",
    "askingprice": "asking_price",
    "pointofpurchase": "point_of_purchase",
    "buydate": "buy_date",
    "sellprice": "sell_price",
    "selldate": "sell_date",
    "signed": "signed",
    "remarked": "remarked",
    "condition": "condition",
    "notes": "notes",
    "donotsell": "do_not_sell",
    "reservecount": "reserve_count",
}


def _parse_bool(val: Any) -> bool | None:
    if pd.isna(val):
        return None
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("true", "1", "yes", "y")


def _parse_date(val: Any) -> datetime | None:
    if pd.isna(val):
        return None
    try:
        return pd.to_datetime(val).to_pydatetime()
    except Exception:
        return None


def _parse_float(val: Any) -> float | None:
    if pd.isna(val):
        return None
    try:
        return float(str(val).replace("$", "").replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _parse_int(val: Any) -> int | None:
    if pd.isna(val):
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip().lower().replace(" ", "").replace("_", "") for c in df.columns]
    return df


_DELIM_CHARS = ",\t;|"


def _is_blank_line(line: str) -> bool:
    """True once delimiter characters and whitespace are stripped away -
    catches spreadsheet-export rows like ',,,,,,,,,,' that have no real
    content but aren't literally empty strings, so pandas' own blank-line
    skipping (which only catches truly empty lines) won't skip them."""
    return not line.translate(str.maketrans("", "", _DELIM_CHARS)).strip()


def _sniff_delimiter_and_header(file_bytes: bytes) -> tuple[str, int]:
    """Returns (delimiter, header_row_index). Handles two real-world export
    quirks instead of assuming comma-delimited with the header on line 1:
    - A file exported/copied as tab- or semicolon-separated (common from
      Excel/Sheets/Numbers) would otherwise have its entire header read as a
      single column by pandas' comma-only default.
    - Some exports (seen from Numbers/Excel on Mac) prepend fully-empty rows
      before the real header, so pandas would grab an all-empty row as the
      header instead.
    Both surface as a confusing "missing required column: series" error
    rather than the real problem, so we sniff past blank lines for both the
    delimiter and the actual header row."""
    try:
        sample = file_bytes[:8192].decode("utf-8-sig", errors="ignore")
    except Exception:
        return ",", 0

    real_lines = [(i, line) for i, line in enumerate(sample.splitlines()) if not _is_blank_line(line)]
    if not real_lines:
        return ",", 0

    header_row = real_lines[0][0]
    try:
        sniff_sample = "\n".join(line for _, line in real_lines[:5])
        delimiter = csv.Sniffer().sniff(sniff_sample, delimiters=_DELIM_CHARS).delimiter
    except Exception:
        delimiter = ","
    return delimiter, header_row


def parse_csv(file_bytes: bytes, filename: str) -> tuple[list[dict], list[dict]]:
    """
    Returns (rows, errors) where rows are clean dicts ready for DB insertion.
    errors are dicts with {row, comic, error}.
    """
    try:
        delimiter, header_row = _sniff_delimiter_and_header(file_bytes)
        df = pd.read_csv(io.BytesIO(file_bytes), dtype=str, keep_default_na=False, sep=delimiter, header=header_row)
    except Exception as e:
        return [], [{"row": 0, "comic": "", "error": f"Could not parse CSV: {e}"}]

    df = _normalize_headers(df)
    df = df.replace("", None)

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        return [], [{"row": 0, "comic": "", "error": f"Missing required columns: {missing}"}]

    rows = []
    errors = []

    for idx, raw_row in df.iterrows():
        row_num = idx + header_row + 2  # 1-based + header (header may not be on line 1, see _sniff_delimiter_and_header)
        row = {"_row_num": row_num}
        # A blank cell reads back as NaN (float), not "" - guard so a blank
        # series/issue number shows as "" in error labels rather than "nan".
        series_val, issue_val = raw_row.get("series"), raw_row.get("issuenumber")
        comic_label = f"{series_val if pd.notna(series_val) else ''} #{issue_val if pd.notna(issue_val) else ''}"

        try:
            for csv_col, db_col in COLUMN_MAP.items():
                val = raw_row.get(csv_col)

                if csv_col in BOOLEAN_FIELDS:
                    row[db_col] = _parse_bool(val)
                elif csv_col in FLOAT_FIELDS:
                    row[db_col] = _parse_float(val)
                elif csv_col == "count":
                    row[db_col] = _parse_int(val) or 1
                elif csv_col in INT_FIELDS:
                    row[db_col] = _parse_int(val) or 0
                elif csv_col in DATE_FIELDS:
                    row[db_col] = _parse_date(val)
                else:
                    # A genuinely empty cell reads back from pandas as NaN
                    # (a float), not "" - even with keep_default_na=False,
                    # which only controls recognized NA *strings*, not truly
                    # blank fields. Every other branch above already guards
                    # this via pd.isna() in its own parser helper; this one
                    # didn't, so a blank cell here (any plain string field -
                    # publisher, writer, etc.) came out as `nan` rather than
                    # None. Also strips actual string values on the way in.
                    row[db_col] = None if pd.isna(val) else (str(val).strip() or None)

            if not row.get("series"):
                errors.append({"row": row_num, "comic": comic_label, "error": "Missing required field: series"})
                continue
            if not row.get("issue_number"):
                errors.append({"row": row_num, "comic": comic_label, "error": "Missing required field: issue number"})
                continue

            rows.append(row)

        except Exception as e:
            errors.append({"row": row_num, "comic": comic_label, "error": str(e)})

    return rows, errors
