from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app import crud, gcd_lookup
from app.auth import get_current_non_kiosk
from app.database import get_db
from app.gcd_database import get_gcd_db
from app.models import User
from app.schemas import CSVImportConflictOut, CSVImportResult, ComicCreate, SaleCreate, UserComicCreate
from app.utils.csv_parser import parse_csv

router = APIRouter(prefix="/uploads", tags=["uploads"])

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/csv", response_model=CSVImportResult)
async def upload_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    gcd_db: Session | None = Depends(get_gcd_db),
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

    # Created early (placeholder stats) so conflicts found during the loop
    # below can reference this import's id; stats get filled in at the end.
    csv_import = crud.create_csv_import(
        db, user_id=current_user.id, filename=file.filename,
        total=len(rows) + len(parse_errors), success=0, failed=0, errors=[],
    )

    imported = 0
    new_added = 0
    linked = 0
    sales_recorded = 0
    conflicts_queued = 0
    declined: list[dict] = []
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
                "newstand": row.get("newstand"),
                "print_run": row.get("print_run"),
                "variant": row.get("variant"),
                "cover_letter": row.get("cover_letter"),
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
                conflicts: list[tuple[str, str, str]] = []
                if gcd_db is not None:
                    conflicts, found = gcd_lookup.enrich_comic_from_gcd(db, gcd_db, comic_data)
                    if not found:
                        declined.append({
                            "row": row.get("_row_num", "?"),
                            "series": comic_data["series"],
                            "issue_number": comic_data.get("issue_number"),
                        })
                comic = crud.create_comic(db, ComicCreate(**comic_data), user_id=current_user.id)
                new_added += 1
                for field_name, csv_value, gcd_value in conflicts:
                    crud.create_csv_conflict(
                        db, current_user.id, csv_import.id, comic.id, field_name, csv_value, gcd_value,
                    )
                    conflicts_queued += 1

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
                reserve_count=row.get("reserve_count") or 0,
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
    crud.update_csv_import_stats(
        db, csv_import.id,
        successful_imports=imported,
        failed_rows=len(row_errors),
        error_log=row_errors,
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
        declined=declined,
        conflicts_queued=conflicts_queued,
    )


@router.get("/history")
def get_upload_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    return crud.get_user_csv_imports(db, current_user.id)


@router.get("/conflicts", response_model=list[CSVImportConflictOut])
def list_csv_conflicts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    conflicts = crud.get_pending_csv_conflicts(db, current_user.id)
    return [
        CSVImportConflictOut(
            id=c.id,
            comic_id=c.comic_id,
            comic_series=c.comic.series,
            comic_issue_number=c.comic.issue_number,
            field_name=c.field_name,
            csv_value=c.csv_value,
            gcd_value=c.gcd_value,
            created_at=c.created_at,
        )
        for c in conflicts
    ]


@router.post("/conflicts/{conflict_id}/accept", response_model=CSVImportConflictOut)
def accept_csv_conflict(
    conflict_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    conflict = crud.resolve_csv_conflict(db, current_user.id, conflict_id, accept=True)
    if not conflict:
        raise HTTPException(status_code=404, detail="Conflict not found")
    return CSVImportConflictOut(
        id=conflict.id, comic_id=conflict.comic_id, comic_series=conflict.comic.series,
        comic_issue_number=conflict.comic.issue_number, field_name=conflict.field_name,
        csv_value=conflict.csv_value, gcd_value=conflict.gcd_value, created_at=conflict.created_at,
    )


@router.post("/conflicts/{conflict_id}/reject", response_model=CSVImportConflictOut)
def reject_csv_conflict(
    conflict_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_non_kiosk),
):
    conflict = crud.resolve_csv_conflict(db, current_user.id, conflict_id, accept=False)
    if not conflict:
        raise HTTPException(status_code=404, detail="Conflict not found")
    return CSVImportConflictOut(
        id=conflict.id, comic_id=conflict.comic_id, comic_series=conflict.comic.series,
        comic_issue_number=conflict.comic.issue_number, field_name=conflict.field_name,
        csv_value=conflict.csv_value, gcd_value=conflict.gcd_value, created_at=conflict.created_at,
    )
