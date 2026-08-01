from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import crud
from app.auth import get_current_user
from app.database import get_db
from app.models import User, UserComic
from app.schemas import KioskCardOut, KioskSignupCreate, KioskSignupOut, SeriesSearchResult

router = APIRouter(prefix="/kiosk", tags=["kiosk"])

FEATURED_LIMIT = 25
TODAYS_PICKS_PRICE_THRESHOLD = 100.0


def _to_card(uc: UserComic) -> KioskCardOut:
    comic = uc.comic
    return KioskCardOut(
        id=uc.id,
        series=comic.series,
        volume=comic.volume,
        issue_number=comic.issue_number,
        legacy_number=comic.legacy_number,
        cover_date=comic.cover_date,
        publisher=comic.publisher,
        variant=comic.variant,
        img=comic.master_photo or comic.img,
        cover_artist=comic.cover_artist,
        penciller=comic.penciller,
        inker=comic.inker,
        writer=comic.writer,
        direct=comic.direct,
        print_run=comic.print_run,
        average_price=comic.average_price,
        signed=uc.signed,
        remarked=uc.remarked,
        condition=uc.condition,
        available=(uc.count or 1) - len(uc.sales),
    )


def _resolve_featured(db: Session, section: str, query_fresh) -> list[UserComic]:
    cached_ids = crud.get_fresh_featured_ids(db, section)
    if cached_ids is not None:
        items = crud.get_user_comics_by_ids(db, cached_ids)
        if items:
            return items
    items = query_fresh(FEATURED_LIMIT)
    crud.set_featured_ids(db, section, [item.id for item in items])
    return items


@router.post("/signup", response_model=KioskSignupOut, status_code=201)
def kiosk_signup(
    payload: KioskSignupCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return crud.upsert_kiosk_signup(
        db,
        payload.first_name.strip(),
        payload.last_name.strip(),
        payload.email.strip().lower(),
        payload.phone.strip() if payload.phone else None,
    )


@router.get("/featured/todays-picks", response_model=list[KioskCardOut])
def kiosk_todays_picks(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    items = _resolve_featured(
        db,
        "todays_picks",
        lambda limit: crud.get_kiosk_available_by_price(db, TODAYS_PICKS_PRICE_THRESHOLD, limit),
    )
    return [_to_card(uc) for uc in items]


@router.get("/featured/signed", response_model=list[KioskCardOut])
def kiosk_signed_comics(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    items = _resolve_featured(
        db,
        "signed",
        lambda limit: crud.get_kiosk_available_signed(db, limit),
    )
    return [_to_card(uc) for uc in items]


@router.get("/series/search", response_model=list[SeriesSearchResult])
def kiosk_series_search(
    q: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return [SeriesSearchResult(**r) for r in crud.search_kiosk_series(db, q)]


@router.get("/series/items", response_model=list[KioskCardOut])
def kiosk_series_items(
    name: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    items = crud.get_kiosk_items_by_series(db, name)
    return [_to_card(uc) for uc in items]
