from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app import crud
from app.auth import get_current_non_kiosk
from app.database import get_db
from app.models import User
from app.schemas import CSVImportResult, ComicCreate, SaleCreate, UserComicCreate
from app.utils.csv_parser import parse_csv

router = APIRouter(prefix="/uploads", tags=["uploads"])

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/csv", response_model=CSVImportResult)
async def upload_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    rows, parse_errors = parse_csv(contents, file.filename)

    if not rows and parse_errors:
        raise HTTPException(status_code=422, detail=parse_errors[0]["error"])

    imported = 0
    new_added = 0
    linked = 0
    sales_recorded = 0
    row_errors = list(parse_errors)

    for row in rows:
        try:
            comic_data = {
                "upc": row.get("upc"),
                "img": row.get("img"),
                "publisher": row.get("publisher"),
                "series": row["series"],
                "volume": row.get("volume"),
                "issue_number": row.get("issue_number"),
                "legacy_number": row.get("legacy_number"),
                "cover_date": row.get("cover_date"),
                "store_date": row.get("store_date"),
                "direct": row.get("direct"),
                "print_run": row.get("print_run"),
                "variant": row.get("variant"),
                "writer": row.get("writer"),
                "penciller": row.get("penciller"),
                "inker": row.get("inker"),
                "cover_artist": row.get("cover_artist"),
                "average_price": row.get("average_price"),
            }

            existing = crud.find_matching_comic(db, {
                "series": comic_data["series"],
                "publisher": comic_data["publisher"],
                "volume": comic_data["volume"],
                "issue_number": comic_data["issue_number"],
                "variant": comic_data["variant"],
                "print_run": comic_data["print_run"],
                "upc": comic_data["upc"],
            })

            if existing:
                comic = existing
                linked += 1
            else:
                comic = crud.create_comic(db, ComicCreate(**comic_data), user_id=current_user.id)
                new_added += 1

            if crud.user_already_owns(db, current_user.id, comic.id):
                row_errors.append({
                    "row": row.get("_row_num", "?"),
                    "comic": row.get("series", "unknown"),
                    "error": "Duplicate: already in your collection",
                })
                continue

            uc_data = UserComicCreate(
                comic_id=comic.id,
                count=row.get("count") or 1,
                paid_price=row.get("paid_price"),
                asking_price=row.get("asking_price"),
                point_of_purchase=row.get("point_of_purchase"),
                buy_date=row.get("buy_date"),
                signed=row.get("signed") or False,
                remarked=row.get("remarked") or False,
                notes=row.get("notes"),
                do_not_sell=row.get("do_not_sell") or False,
            )
            uc = crud.create_user_comic(db, current_user.id, uc_data)
            imported += 1

            if row.get("sell_price") is not None:
                sale = crud.create_sale(db, current_user.id, uc.id, SaleCreate(
                    sell_date=row.get("sell_date") or datetime.utcnow(),
                    sell_price=row.get("sell_price"),
                ))
                if sale is None:
                    row_errors.append({
                        "row": row.get("_row_num", "?"),
                        "comic": row.get("series", "unknown"),
                        "error": "Could not record sale: all copies already sold",
                    })
                else:
                    sales_recorded += 1

        except Exception as e:
            row_errors.append({
                "row": "?",
                "comic": row.get("series", "unknown"),
                "error": str(e),
            })

    crud.record_snapshot(db, current_user.id)
    crud.create_csv_import(
        db,
        user_id=current_user.id,
        filename=file.filename,
        total=len(rows) + len(parse_errors),
        success=imported,
        failed=len(row_errors),
        errors=row_errors,
    )

    return CSVImportResult(
        success=True,
        filename=file.filename,
        total_rows=len(rows) + len(parse_errors),
        imported=imported,
        failed=len(row_errors),
        new_comics_added_to_db=new_added,
        existing_comics_linked=linked,
        sales_recorded=sales_recorded,
        errors=row_errors,
    )


@router.get("/history")
def get_upload_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    return crud.get_user_csv_imports(db, current_user.id)
