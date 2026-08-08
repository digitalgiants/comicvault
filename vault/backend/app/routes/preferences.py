from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import crud, crud_cards
from app.auth import get_current_user
from app.database import get_db
from app.models import User
from app.schemas import ColumnPreferenceOut, ColumnPreferenceUpdate

router = APIRouter(prefix="/users/preferences", tags=["preferences"])

_DEFAULTS_BY_PAGE = {
    "sold": crud.DEFAULT_SOLD_COLUMNS,
    "cards": crud_cards.DEFAULT_CARDS_COLUMNS,
}


@router.get("/columns/{page}", response_model=ColumnPreferenceOut)
def get_column_prefs(
    page: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pref = crud.get_column_preference(db, current_user.id, page)
    if pref:
        return ColumnPreferenceOut(page=pref.page, columns=pref.columns)
    defaults = _DEFAULTS_BY_PAGE.get(page, crud.DEFAULT_COLLECTION_COLUMNS)
    return ColumnPreferenceOut(page=page, columns=defaults)


@router.put("/columns/{page}", response_model=ColumnPreferenceOut)
def update_column_prefs(
    page: str,
    body: ColumnPreferenceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pref = crud.upsert_column_preference(db, current_user.id, page, body.columns)
    return ColumnPreferenceOut(page=pref.page, columns=pref.columns)
