import io
from datetime import datetime
from typing import Any

import pandas as pd

REQUIRED_COLUMNS = {"series"}

BOOLEAN_FIELDS = {"newstand/direct", "signed", "remarked", "donotsell"}
FLOAT_FIELDS = {"paidprice", "averageprice", "sellprice", "askingprice"}
INT_FIELDS = {"count"}
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
    "newstand/direct": "direct",
    "publisher": "publisher",
    "count": "count",
    "printrun": "print_run",
    "variant": "variant",
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
    "notes": "notes",
    "donotsell": "do_not_sell",
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


def parse_csv(file_bytes: bytes, filename: str) -> tuple[list[dict], list[dict]]:
    """
    Returns (rows, errors) where rows are clean dicts ready for DB insertion.
    errors are dicts with {row, comic, error}.
    """
    try:
        df = pd.read_csv(io.BytesIO(file_bytes), dtype=str, keep_default_na=False)
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
        row_num = idx + 2  # 1-based + header
        row = {}
        comic_label = f"{raw_row.get('series', '')} #{raw_row.get('issuenumber', '')}"

        try:
            for csv_col, db_col in COLUMN_MAP.items():
                val = raw_row.get(csv_col)

                if csv_col in BOOLEAN_FIELDS:
                    row[db_col] = _parse_bool(val)
                elif csv_col in FLOAT_FIELDS:
                    row[db_col] = _parse_float(val)
                elif csv_col in INT_FIELDS:
                    row[db_col] = _parse_int(val) or 1
                elif csv_col in DATE_FIELDS:
                    row[db_col] = _parse_date(val)
                else:
                    row[db_col] = val if val and str(val).strip() else None

            if not row.get("series"):
                errors.append({"row": row_num, "comic": comic_label, "error": "Missing required field: series"})
                continue

            rows.append(row)

        except Exception as e:
            errors.append({"row": row_num, "comic": comic_label, "error": str(e)})

    return rows, errors
