from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import crud, crud_cards
from app.auth import get_current_user
from app.database import get_db
from app.models import User, UserComic, UserTradingCard
from app.schemas import (
    KioskCardOut, KioskSignupCreate, KioskSignupOut, KioskTradingCardOut, SeriesSearchResult,
)

router = APIRouter(prefix="/kiosk", tags=["kiosk"])

# Price thresholds, per-section refresh intervals, and the featured-item
# count are all admin-configurable (see KioskSettings / /admin/kiosk-settings)
# - no hardcoded defaults here.


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
        newstand=comic.newstand,
        print_run=comic.print_run,
        signed=uc.signed,
        remarked=uc.remarked,
        condition=uc.condition,
        available=max(0, (uc.count or 1) - len(uc.sales) - (uc.reserve_count or 0)),
    )


def _to_kiosk_trading_card(uc: UserTradingCard) -> KioskTradingCardOut:
    card = uc.card
    return KioskTradingCardOut(
        id=uc.id,
        name=card.name,
        game_name=card.game_name,
        set_name=card.set_name,
        card_number=card.card_number,
        rarity=card.rarity,
        img=card.master_photo or card.image_large or card.image_medium or card.image_small,
        available=max(0, (uc.count or 1) - len(uc.sales) - (uc.reserve_count or 0)),
    )


def _resolve_featured(db: Session, section: str, query_fresh, ttl_minutes: int, limit: int, get_by_ids=crud.get_user_comics_by_ids) -> list:
    """Generic over comics/cards - get_by_ids defaults to the comics lookup
    for existing callers, pass crud_cards.get_user_trading_cards_by_ids for
    cards sections."""
    cached_ids = crud.get_fresh_featured_ids(db, section, ttl_minutes)
    if cached_ids is not None:
        items = get_by_ids(db, cached_ids)
        if items:
            return items
    items = query_fresh(limit)
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
    settings = crud.get_kiosk_settings(db)
    items = _resolve_featured(
        db,
        "todays_picks",
        lambda limit: crud.get_kiosk_available_by_price(db, settings.comics_price_threshold, limit),
        settings.todays_picks_refresh_minutes,
        settings.featured_limit,
    )
    return [_to_card(uc) for uc in items]


@router.get("/featured/signed", response_model=list[KioskCardOut])
def kiosk_signed_comics(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    settings = crud.get_kiosk_settings(db)
    items = _resolve_featured(
        db,
        "signed",
        lambda limit: crud.get_kiosk_available_signed(db, limit),
        settings.signed_refresh_minutes,
        settings.featured_limit,
    )
    return [_to_card(uc) for uc in items]


@router.get("/browse/todays-picks", response_model=list[KioskCardOut])
def kiosk_browse_todays_picks(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    settings = crud.get_kiosk_settings(db)
    items = crud.get_all_kiosk_available_by_price(db, settings.comics_price_threshold)
    return [_to_card(uc) for uc in items]


@router.get("/browse/signed", response_model=list[KioskCardOut])
def kiosk_browse_signed_comics(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    items = crud.get_all_kiosk_available_signed(db)
    return [_to_card(uc) for uc in items]


@router.get("/series/search", response_model=list[SeriesSearchResult])
def kiosk_series_search(
    q: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    crud.log_kiosk_search(db, q, "comics")
    return [SeriesSearchResult(**r) for r in crud.search_kiosk_series(db, q)]


@router.get("/series/items", response_model=list[KioskCardOut])
def kiosk_series_items(
    name: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    items = crud.get_kiosk_items_by_series(db, name)
    return [_to_card(uc) for uc in items]


# --- Kiosk: trading cards (separate section from comics above, not merged
# into the same feed - see feature-requests/tcg_card_scanner_build_prompt.md) ---

@router.get("/cards/featured/todays-picks", response_model=list[KioskTradingCardOut])
def kiosk_cards_todays_picks(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    settings = crud.get_kiosk_settings(db)
    items = _resolve_featured(
        db,
        "cards_todays_picks",
        lambda limit: crud_cards.get_kiosk_cards_available_by_price(db, settings.cards_price_threshold, limit),
        settings.cards_todays_picks_refresh_minutes,
        settings.featured_limit,
        get_by_ids=crud_cards.get_user_trading_cards_by_ids,
    )
    return [_to_kiosk_trading_card(uc) for uc in items]


@router.get("/cards/featured/graded", response_model=list[KioskTradingCardOut])
def kiosk_cards_graded(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    settings = crud.get_kiosk_settings(db)
    items = _resolve_featured(
        db,
        "cards_graded",
        lambda limit: crud_cards.get_kiosk_cards_graded(db, limit),
        settings.cards_graded_refresh_minutes,
        settings.featured_limit,
        get_by_ids=crud_cards.get_user_trading_cards_by_ids,
    )
    return [_to_kiosk_trading_card(uc) for uc in items]


@router.get("/cards/browse/todays-picks", response_model=list[KioskTradingCardOut])
def kiosk_cards_browse_todays_picks(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    settings = crud.get_kiosk_settings(db)
    items = crud_cards.get_all_kiosk_cards_available_by_price(db, settings.cards_price_threshold)
    return [_to_kiosk_trading_card(uc) for uc in items]


@router.get("/cards/browse/graded", response_model=list[KioskTradingCardOut])
def kiosk_cards_browse_graded(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    items = crud_cards.get_all_kiosk_cards_graded(db)
    return [_to_kiosk_trading_card(uc) for uc in items]


@router.get("/cards/search", response_model=list[SeriesSearchResult])
def kiosk_cards_search(
    q: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    crud.log_kiosk_search(db, q, "cards")
    return [SeriesSearchResult(**r) for r in crud_cards.search_kiosk_cards(db, q)]


@router.get("/cards/items", response_model=list[KioskTradingCardOut])
def kiosk_cards_items(
    name: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    items = crud_cards.get_kiosk_cards_by_name(db, name)
    return [_to_kiosk_trading_card(uc) for uc in items]
