from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app import crud
from app.auth import get_current_non_kiosk
from app.database import get_db
from app.models import User
from app.schemas import CSVImportResult, ComicCreate, UserComicCreate
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
    row_errors = list(parse_errors)

    for row in rows:
        try:
            comic_data = {
                "publisher": row.get("publisher"),
                "name": row["name"],
                "volume": row.get("volume"),
                "number": row.get("number"),
                "print": row.get("print"),
                "cover": row.get("cover"),
                "variant": row.get("variant"),
                "direct": row.get("direct"),
                "writer": row.get("writer"),
                "artist": row.get("artist"),
                "pencils": row.get("pencils"),
                "inker": row.get("inker"),
                "cover_artist": row.get("cover_artist"),
                "average_price": row.get("average_price"),
                "print_ratio": row.get("print_ratio"),
            }

            existing = crud.find_matching_comic(db, {
                "name": comic_data["name"],
                "publisher": comic_data["publisher"],
                "volume": comic_data["volume"],
                "number": comic_data["number"],
                "variant": comic_data["variant"],
                "print": comic_data["print"],
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
                    "comic": row.get("name", "unknown"),
                    "error": "Duplicate: already in your collection",
                })
                continue

            uc_data = UserComicCreate(
                comic_id=comic.id,
                number_of_books=row.get("number_of_books") or 1,
                price_paid=row.get("price_paid"),
                point_of_purchase=row.get("point_of_purchase"),
                buy_date=row.get("buy_date"),
                signed=row.get("signed") or False,
                remarked=row.get("remarked") or False,
                notes=row.get("notes"),
            )
            crud.create_user_comic(db, current_user.id, uc_data)
            imported += 1

        except Exception as e:
            row_errors.append({
                "row": "?",
                "comic": row.get("name", "unknown"),
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
        errors=row_errors,
    )


@router.get("/history")
def get_upload_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    return crud.get_user_csv_imports(db, current_user.id)
