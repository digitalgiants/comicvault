import io
from datetime import datetime
from typing import Any

import pandas as pd

REQUIRED_COLUMNS = {"name"}

BOOLEAN_FIELDS = {"direct", "signed", "remarked"}
FLOAT_FIELDS = {"pricePaid", "averagePrice"}
INT_FIELDS = {"numberOfBooks"}
DATE_FIELDS = {"buyDate", "sellDate"}

COLUMN_MAP = {
    "publisher": "publisher",
    "name": "name",
    "volume": "volume",
    "number": "number",
    "print": "print",
    "cover": "cover",
    "variant": "variant",
    "direct": "direct",
    "writer": "writer",
    "artist": "artist",
    "pencils": "pencils",
    "inker": "inker",
    "coverartist": "cover_artist",
    "numberofbooks": "number_of_books",
    "pricepaid": "price_paid",
    "pointofpurchase": "point_of_purchase",
    "buydate": "buy_date",
    "averageprice": "average_price",
    "printratio": "print_ratio",
    "signed": "signed",
    "remarked": "remarked",
    "notes": "notes",
    "selldate": "sell_date",
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
        comic_label = f"{raw_row.get('name', '')} #{raw_row.get('number', '')}"

        try:
            for csv_col, db_col in COLUMN_MAP.items():
                val = raw_row.get(csv_col)

                if csv_col in ("direct", "signed", "remarked"):
                    row[db_col] = _parse_bool(val)
                elif csv_col in ("pricepaid", "averageprice"):
                    row[db_col] = _parse_float(val)
                elif csv_col == "numberofbooks":
                    row[db_col] = _parse_int(val) or 1
                elif csv_col in ("buydate", "selldate"):
                    row[db_col] = _parse_date(val)
                else:
                    row[db_col] = val if val and str(val).strip() else None

            if not row.get("name"):
                errors.append({"row": row_num, "comic": comic_label, "error": "Missing required field: name"})
                continue

            rows.append(row)

        except Exception as e:
            errors.append({"row": row_num, "comic": comic_label, "error": str(e)})

    return rows, errors
