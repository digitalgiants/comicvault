from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, crud_cards
from app.auth import get_current_admin
from app.config import settings
from app.database import get_db
from app.models import TradingCard, User
from app.schemas import (
    BugReportOut, ComicCreate, ComicOut, ComicUpdate, TradingCardCreate,
    TradingCardOut, TradingCardUpdate, UserOut, UserUpdate,
)

router = APIRouter(prefix="/admin", tags=["admin"])

SYNC_TIMEOUT = 60.0  # tcg-scraper calls out to apitcg.com and paginates - can be slow
MAX_SYNC_PAGES = 50  # safety cap - apitcg's pagination correctness is unverified


@router.get("/users", response_model=list[UserOut])
def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    return crud.get_all_users(db, skip=skip, limit=limit)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    update: UserUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    user = None
    if update.is_admin is not None:
        user = crud.set_user_admin(db, user_id, update.is_admin)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
    if update.is_kiosk is not None:
        user = crud.set_user_kiosk(db, user_id, update.is_kiosk)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
    if user is None:
        raise HTTPException(status_code=400, detail="Nothing to update")
    return user


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    if not crud.delete_user(db, user_id):
        raise HTTPException(status_code=404, detail="User not found")


@router.post("/comics", response_model=ComicOut, status_code=201)
def add_comic(
    comic_in: ComicCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    return crud.create_comic(db, comic_in, user_id=admin.id)


@router.patch("/comics/{comic_id}", response_model=ComicOut)
def update_comic(
    comic_id: int,
    update: ComicUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    comic = crud.update_comic(db, comic_id, update)
    if not comic:
        raise HTTPException(status_code=404, detail="Comic not found")
    return comic


@router.get("/comics", response_model=list[ComicOut])
def list_comics(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    from app.models import Comic
    return db.query(Comic).offset(skip).limit(limit).all()


@router.delete("/comics/{comic_id}", status_code=204)
def delete_comic(
    comic_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    from app.models import Comic
    comic = db.query(Comic).filter(Comic.id == comic_id).first()
    if not comic:
        raise HTTPException(status_code=404, detail="Comic not found")
    db.delete(comic)
    db.commit()


@router.get("/bug-reports", response_model=list[BugReportOut])
def list_bug_reports(
    resolved: Optional[bool] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    reports = crud.get_all_bug_reports(db, resolved=resolved)
    return [
        BugReportOut(
            id=r.id,
            text=r.text,
            comic_id=r.comic_id,
            page_url=r.page_url,
            resolved=r.resolved,
            created_at=r.created_at,
            user_username=r.user.username,
            comic_name=r.comic.series if r.comic else None,
        )
        for r in reports
    ]


@router.patch("/bug-reports/{report_id}/resolve", response_model=dict)
def resolve_bug_report(
    report_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    report = crud.resolve_bug_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"success": True}


# --- Trading cards catalog (manual admin CRUD) ---

@router.post("/cards", response_model=TradingCardOut, status_code=201)
def add_card(
    card_in: TradingCardCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    return crud_cards.create_trading_card(db, card_in, user_id=admin.id)


@router.patch("/cards/{card_id}", response_model=TradingCardOut)
def update_card(
    card_id: int,
    update: TradingCardUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    card = crud_cards.update_trading_card_metadata(db, card_id, update)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


@router.get("/cards", response_model=list[TradingCardOut])
def list_cards(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    return db.query(TradingCard).offset(skip).limit(limit).all()


@router.delete("/cards/{card_id}", status_code=204)
def delete_card(
    card_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    if not crud_cards.delete_trading_card(db, card_id):
        raise HTTPException(status_code=404, detail="Card not found")


# --- Trading cards catalog sync (apitcg.com via tcg-scraper) ---
# Sync order is enforced, not assumed: games -> sets -> products, since
# products FK to sets which FK to games. Each step validates its parent
# already exists locally rather than silently creating thin placeholder
# rows - calling these out of order fails loudly instead of producing bad
# data. No "sync everything" bulk endpoint - there's no background job
# runner anywhere in this app, so each call stays scoped to one game or
# one set and completes within a normal request.

@router.post("/cards/sync/games", response_model=dict)
def sync_card_games(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    try:
        resp = httpx.get(f"{settings.tcg_scraper_url}/games", timeout=SYNC_TIMEOUT)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"tcg-scraper unavailable: {exc}")

    games = resp.json()
    for g in games:
        crud_cards.upsert_game(db, g["external_id"], g["name"], g.get("logo_image_url"))
    return {"synced": len(games)}


@router.post("/cards/sync/sets", response_model=dict)
def sync_card_sets(
    game_slug: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    game = crud_cards.get_game_by_slug(db, game_slug)
    if game is None:
        raise HTTPException(
            status_code=400,
            detail=f"Game '{game_slug}' hasn't been synced yet - run /admin/cards/sync/games first",
        )

    try:
        resp = httpx.get(f"{settings.tcg_scraper_url}/games/{game_slug}/sets", timeout=SYNC_TIMEOUT)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"tcg-scraper unavailable: {exc}")

    sets = resp.json()
    for s in sets:
        # series_id intentionally left unset - apitcg's /sets shape hasn't
        # confirmed a series *name* field (only a possible series id), and
        # fabricating a series name from an opaque id would pollute the
        # catalog. CardSet.series_id is nullable for exactly this reason.
        crud_cards.upsert_set(
            db, game.id, s["name"], external_id=s.get("external_id"), set_code=s.get("set_code"),
            printed_total=s.get("printed_total"), total_cards=s.get("total_cards"),
            release_date=s.get("release_date"),
        )
    return {"synced": len(sets)}


@router.post("/cards/sync/products", response_model=dict)
def sync_card_products(
    game_slug: str,
    set_external_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    game = crud_cards.get_game_by_slug(db, game_slug)
    if game is None:
        raise HTTPException(
            status_code=400,
            detail=f"Game '{game_slug}' hasn't been synced yet - run /admin/cards/sync/games first",
        )
    card_set = crud_cards.get_set_by_external_id(db, game.id, set_external_id)
    if card_set is None:
        raise HTTPException(
            status_code=400,
            detail=f"Set '{set_external_id}' hasn't been synced yet - run /admin/cards/sync/sets first",
        )

    total_synced = 0
    page = 1
    while page <= MAX_SYNC_PAGES:
        try:
            resp = httpx.get(
                f"{settings.tcg_scraper_url}/games/{game_slug}/sets/{set_external_id}/products",
                params={"page": page, "limit": 250},
                timeout=SYNC_TIMEOUT,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"tcg-scraper unavailable: {exc}")

        data = resp.json()
        for item in data["items"]:
            crud_cards.upsert_trading_card_from_sync(db, card_set, item)
        total_synced += len(data["items"])

        if not data.get("has_more"):
            break
        page += 1

    return {"synced": total_synced}
