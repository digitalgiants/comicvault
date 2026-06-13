from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import crud
from app.auth import get_current_user
from app.database import get_db
from app.models import User
from app.schemas import BugReportCreate, BugReportOut

router = APIRouter(prefix="/bug-reports", tags=["bug-reports"])


@router.post("/", response_model=dict, status_code=201)
def submit_bug_report(
    report_in: BugReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    crud.create_bug_report(db, current_user.id, report_in)
    return {"success": True}
