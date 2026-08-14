"""CRUD for the trading-cards feature - kept separate from crud.py (already
~900 lines) rather than a nested per-feature package, matching this
codebase's flat-file convention (see feature-requests/tcg_card_scanner_build_prompt.md)."""
import difflib
import random
import re
from datetime import date, datetime
from typing import Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from app.crud import MASTER_PHOTO_OWNER_USERNAME
from app.models import (
    CardGame, CardGrade, CardSeries, CardSet, CardTransaction, IdentificationMatch,
    IdentificationScan, TradingCard, TradingCardExternalId, User, UserTradingCard,
)
from app.schemas import (
    CardSaleCreate, CardSaleUpdate, TradingCardCreate, TradingCardUpdate,
    UserTradingCardCreate, UserTradingCardUpdate,
)

DEFAULT_CARDS_COLUMNS: dict[str, bool] = {
    "image_small": True, "name": True, "game_name": True, "set_name": True,
    "card_number": True, "rarity": True, "count": True, "condition": True,
    "average_price": True, "paid_price": True, "asking_price": True,
    "point_of_purchase": True, "buy_date": True, "notes": True,
}


def _parse_date(value) -> Optional[date]:
    """apitcg.com's release_date format is unverified - parse defensively,
    never let a sync job crash on an unexpected date string."""
    if value is None or isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


# --- Catalog (games / series / sets) ---

def get_game_by_slug(db: Session, slug: str) -> Optional[CardGame]:
    return db.query(CardGame).filter(CardGame.slug == slug).first()


def list_games(db: Session) -> list[CardGame]:
    return db.query(CardGame).order_by(CardGame.name).all()


def upsert_game(db: Session, slug: str, name: str, logo_image_url: Optional[str] = None) -> CardGame:
    """Top-level sync entry point - no parent to validate, unlike
    series/sets/cards below."""
    game = get_game_by_slug(db, slug)
    if game is None:
        game = CardGame(slug=slug, name=name, logo_image_url=logo_image_url)
        db.add(game)
    else:
        game.name = name
        if logo_image_url:
            game.logo_image_url = logo_image_url
    db.commit()
    db.refresh(game)
    return game


def get_series_by_name(db: Session, game_id: int, name: str) -> Optional[CardSeries]:
    return db.query(CardSeries).filter(CardSeries.game_id == game_id, CardSeries.name == name).first()


def upsert_series(db: Session, game_id: int, name: str, external_id: Optional[str] = None) -> CardSeries:
    """Caller (the sync route) must have already confirmed game_id exists -
    this does not silently create a placeholder game."""
    series = get_series_by_name(db, game_id, name)
    if series is None:
        series = CardSeries(game_id=game_id, name=name, external_id=external_id)
        db.add(series)
    elif external_id:
        series.external_id = external_id
    db.commit()
    db.refresh(series)
    return series


def get_set_by_external_id(db: Session, game_id: int, external_id: str) -> Optional[CardSet]:
    return (
        db.query(CardSet)
        .filter(CardSet.game_id == game_id, CardSet.external_id == external_id)
        .first()
    )


def get_set_by_name(db: Session, game_id: int, name: str, language: str = "English") -> Optional[CardSet]:
    return (
        db.query(CardSet)
        .filter(CardSet.game_id == game_id, CardSet.name == name, CardSet.language == language)
        .first()
    )


def upsert_set(
    db: Session, game_id: int, name: str, series_id: Optional[int] = None,
    external_id: Optional[str] = None, set_code: Optional[str] = None,
    printed_total: Optional[int] = None, total_cards: Optional[int] = None,
    release_date=None, symbol_image_url: Optional[str] = None,
    logo_image_url: Optional[str] = None, language: str = "English",
) -> CardSet:
    """Caller must have already confirmed game_id exists."""
    card_set = (
        get_set_by_external_id(db, game_id, external_id) if external_id
        else get_set_by_name(db, game_id, name, language)
    )
    if card_set is None:
        card_set = CardSet(game_id=game_id, name=name, language=language)
        db.add(card_set)
    card_set.series_id = series_id if series_id is not None else card_set.series_id
    card_set.external_id = external_id or card_set.external_id
    card_set.set_code = set_code or card_set.set_code
    card_set.printed_total = printed_total if printed_total is not None else card_set.printed_total
    card_set.total_cards = total_cards if total_cards is not None else card_set.total_cards
    card_set.release_date = _parse_date(release_date) or card_set.release_date
    card_set.symbol_image_url = symbol_image_url or card_set.symbol_image_url
    card_set.logo_image_url = logo_image_url or card_set.logo_image_url
    db.commit()
    db.refresh(card_set)
    return card_set


# --- Catalog (trading cards) ---

def get_card_by_id(db: Session, card_id: int) -> Optional[TradingCard]:
    return db.query(TradingCard).filter(TradingCard.id == card_id).first()


def get_card_by_external_id(db: Session, source: str, external_id: str) -> Optional[TradingCard]:
    ext = (
        db.query(TradingCardExternalId)
        .filter(TradingCardExternalId.source == source, TradingCardExternalId.external_id == external_id)
        .first()
    )
    return ext.card if ext else None


def find_matching_card(
    db: Session, set_id: int, card_number: Optional[str], language: str = "English",
) -> Optional[TradingCard]:
    q = db.query(TradingCard).filter(TradingCard.set_id == set_id, TradingCard.language == language)
    if card_number is not None:
        q = q.filter(TradingCard.card_number == card_number)
    else:
        q = q.filter(TradingCard.card_number.is_(None))
    return q.first()


def create_trading_card(db: Session, card_in: TradingCardCreate, user_id: Optional[int] = None) -> TradingCard:
    card = TradingCard(**card_in.model_dump(), created_by_user_id=user_id)
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


def update_trading_card_metadata(db: Session, card_id: int, update: TradingCardUpdate) -> Optional[TradingCard]:
    card = get_card_by_id(db, card_id)
    if not card:
        return None
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(card, field, value)
    db.commit()
    db.refresh(card)
    return card


def delete_trading_card(db: Session, card_id: int) -> bool:
    card = get_card_by_id(db, card_id)
    if not card:
        return False
    db.delete(card)
    db.commit()
    return True


def search_trading_cards(
    db: Session,
    name: Optional[str] = None,
    game_slug: Optional[str] = None,
    set_id: Optional[int] = None,
    card_number: Optional[str] = None,
    rarity: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> list[TradingCard]:
    q = db.query(TradingCard)
    if name:
        q = q.filter(TradingCard.name.ilike(f"%{name}%"))
    if game_slug:
        q = q.join(CardGame).filter(CardGame.slug == game_slug)
    if set_id:
        q = q.filter(TradingCard.set_id == set_id)
    if card_number:
        q = q.filter(TradingCard.card_number == card_number)
    if rarity:
        q = q.filter(TradingCard.rarity.ilike(f"%{rarity}%"))
    return q.offset(skip).limit(limit).all()


def upsert_trading_card_from_sync(db: Session, game_id: int, item: dict) -> TradingCard:
    """Natural key is TradingCardExternalId(source='apitcg', external_id) -
    same role as ExternalIssueCache's (provider, provider_issue_id) pairing
    for comics. Falls back to find_matching_card to reconcile a
    manually-added card before creating a new one.

    Resolves/creates the card's set on the fly from the item's own embedded
    set info - every apitcg.com product response embeds its full set object
    (confirmed live, see feature-requests/apitcg-calls), so callers don't
    need to pre-sync sets before syncing products. A set synced separately
    via /admin/cards/sync/sets still enriches this with fields the
    per-product embed doesn't carry (logo/symbol images, printed totals) -
    upsert_set merges rather than overwrites, so running that afterward is
    safe and additive."""
    set_external_id = item.get("set_external_id")
    set_name = item.get("set_name") or set_external_id or "Unknown Set"
    card_set = upsert_set(db, game_id, set_name, external_id=set_external_id, set_code=item.get("set_code"))

    external_id = str(item["external_id"])
    language = item.get("language") or "English"
    card = get_card_by_external_id(db, "apitcg", external_id)

    if card is None:
        card = find_matching_card(db, card_set.id, item.get("card_number"), language)
        if card is not None:
            db.add(TradingCardExternalId(card_id=card.id, source="apitcg", external_id=external_id))

    images = item.get("images") or {}
    if card is None:
        card = TradingCard(
            game_id=card_set.game_id,
            set_id=card_set.id,
            name=item["name"],
            card_number=item.get("card_number"),
            code=item.get("code"),
            rarity=item.get("rarity"),
            language=language,
            description=item.get("description"),
            attributes=item.get("attributes") or {},
            image_small=images.get("small"),
            image_medium=images.get("medium"),
            image_large=images.get("large"),
            release_date=_parse_date(item.get("release_date")),
            average_price=item.get("average_price"),
        )
        db.add(card)
        db.flush()  # need card.id before attaching the external-id row
        db.add(TradingCardExternalId(card_id=card.id, source="apitcg", external_id=external_id))
    else:
        card.name = item.get("name") or card.name
        card.card_number = item.get("card_number") or card.card_number
        card.code = item.get("code") or card.code
        card.rarity = item.get("rarity") or card.rarity
        card.description = item.get("description") or card.description
        if item.get("attributes"):
            card.attributes = item["attributes"]
        card.image_small = images.get("small") or card.image_small
        card.image_medium = images.get("medium") or card.image_medium
        card.image_large = images.get("large") or card.image_large
        card.release_date = _parse_date(item.get("release_date")) or card.release_date
        if item.get("average_price") is not None:
            card.average_price = item["average_price"]

    db.commit()
    db.refresh(card)
    return card


# --- Personal ownership (mirrors UserComic) ---

def user_already_owns_card(db: Session, user_id: int, card_id: int) -> bool:
    return db.query(UserTradingCard).filter(
        UserTradingCard.user_id == user_id, UserTradingCard.card_id == card_id,
    ).first() is not None


def create_user_trading_card(db: Session, user_id: int, uc_in: UserTradingCardCreate) -> UserTradingCard:
    uc = UserTradingCard(user_id=user_id, **uc_in.model_dump())
    db.add(uc)
    db.commit()
    db.refresh(uc)
    return uc


def get_user_trading_card_by_id(db: Session, user_id: int, uc_id: int) -> Optional[UserTradingCard]:
    return (
        db.query(UserTradingCard)
        .filter(UserTradingCard.id == uc_id, UserTradingCard.user_id == user_id)
        .first()
    )


def update_user_trading_card(
    db: Session, user_id: int, uc_id: int, update: UserTradingCardUpdate,
) -> Optional[UserTradingCard]:
    uc = get_user_trading_card_by_id(db, user_id, uc_id)
    if not uc:
        return None
    changes = update.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(uc, field, value)
    db.commit()
    db.refresh(uc)
    if "personal_img" in changes:
        recompute_card_master_photo(db, uc.card_id)
    return uc


def bulk_update_user_trading_cards(db: Session, user_id: int, updates: list[dict]) -> int:
    count = 0
    cards_to_recompute: set[int] = set()
    for item in updates:
        uc = get_user_trading_card_by_id(db, user_id, item["id"])
        if not uc:
            continue
        for field, value in item["update"].items():
            if value is not None:
                setattr(uc, field, value)
        if "personal_img" in item["update"]:
            cards_to_recompute.add(uc.card_id)
        count += 1
    db.commit()
    for card_id in cards_to_recompute:
        recompute_card_master_photo(db, card_id)
    return count


def get_user_card_collection(
    db: Session,
    user_id: int,
    name: Optional[str] = None,
    game_slug: Optional[str] = None,
    skip: int = 0,
    limit: int = 200,
) -> tuple[list[UserTradingCard], int]:
    q = db.query(UserTradingCard).join(TradingCard).filter(UserTradingCard.user_id == user_id)
    if name:
        q = q.filter(TradingCard.name.ilike(f"%{name}%"))
    if game_slug:
        q = q.join(CardGame, TradingCard.game_id == CardGame.id).filter(CardGame.slug == game_slug)
    total = q.count()
    items = q.order_by(TradingCard.name, TradingCard.card_number).offset(skip).limit(limit).all()
    return items, total


def delete_user_trading_card(db: Session, user_id: int, uc_id: int) -> bool:
    uc = get_user_trading_card_by_id(db, user_id, uc_id)
    if not uc:
        return False
    card_id = uc.card_id
    db.delete(uc)
    db.commit()
    recompute_card_master_photo(db, card_id)
    return True


def set_user_trading_card_photo(db: Session, user_id: int, uc_id: int, path: str) -> Optional[UserTradingCard]:
    uc = get_user_trading_card_by_id(db, user_id, uc_id)
    if not uc:
        return None
    uc.personal_img = path
    db.commit()
    db.refresh(uc)
    recompute_card_master_photo(db, uc.card_id)
    return uc


def recompute_card_master_photo(db: Session, card_id: int) -> None:
    """Mirrors crud.recompute_comic_master_photo exactly - a physical photo
    of the card is more trustworthy than a looked-up catalog image."""
    card = get_card_by_id(db, card_id)
    if card is None:
        return

    owner_photo = (
        db.query(UserTradingCard.personal_img)
        .join(User, UserTradingCard.user_id == User.id)
        .filter(
            UserTradingCard.card_id == card_id,
            User.username == MASTER_PHOTO_OWNER_USERNAME,
            UserTradingCard.personal_img.isnot(None),
        )
        .scalar()
    )
    if owner_photo is None:
        owner_photo = (
            db.query(UserTradingCard.personal_img)
            .filter(UserTradingCard.card_id == card_id, UserTradingCard.personal_img.isnot(None))
            .order_by(UserTradingCard.id)
            .limit(1)
            .scalar()
        )

    if card.master_photo != owner_photo:
        card.master_photo = owner_photo
        db.commit()


def backfill_card_master_photos(db: Session) -> None:
    """Idempotent, mirrors crud.backfill_master_photos - called from
    migrate.py on every deploy."""
    card_ids = {
        row[0]
        for row in db.query(UserTradingCard.card_id).filter(UserTradingCard.personal_img.isnot(None)).distinct()
    }
    card_ids |= {row[0] for row in db.query(TradingCard.id).filter(TradingCard.master_photo.isnot(None))}
    for card_id in card_ids:
        recompute_card_master_photo(db, card_id)


# --- Sales (via CardTransaction, transaction_type='Sale') ---

def create_card_sale(db: Session, user_id: int, uc_id: int, sale_in: CardSaleCreate) -> Optional[CardTransaction]:
    uc = get_user_trading_card_by_id(db, user_id, uc_id)
    if not uc:
        return None
    total_copies = uc.count or 1
    if len(uc.sales) >= total_copies:
        return None  # over-sell guard; caller checks for None
    txn = CardTransaction(
        user_trading_card_id=uc_id,
        transaction_type="Sale",
        transaction_date=sale_in.transaction_date,
        price=sale_in.price,
        notes=sale_in.notes,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def update_card_sale(
    db: Session, user_id: int, uc_id: int, txn_id: int, update: CardSaleUpdate,
) -> Optional[CardTransaction]:
    txn = (
        db.query(CardTransaction)
        .join(UserTradingCard, CardTransaction.user_trading_card_id == UserTradingCard.id)
        .filter(
            CardTransaction.id == txn_id,
            CardTransaction.user_trading_card_id == uc_id,
            UserTradingCard.user_id == user_id,
            CardTransaction.transaction_type == "Sale",
        )
        .first()
    )
    if not txn:
        return None
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(txn, field, value)
    db.commit()
    db.refresh(txn)
    return txn


def delete_card_sale(db: Session, user_id: int, uc_id: int, txn_id: int) -> bool:
    txn = (
        db.query(CardTransaction)
        .join(UserTradingCard, CardTransaction.user_trading_card_id == UserTradingCard.id)
        .filter(
            CardTransaction.id == txn_id,
            CardTransaction.user_trading_card_id == uc_id,
            UserTradingCard.user_id == user_id,
            CardTransaction.transaction_type == "Sale",
        )
        .first()
    )
    if not txn:
        return False
    db.delete(txn)
    db.commit()
    return True


# --- Identification scans ---

def create_identification_scan(
    db: Session, user_id: int, image_url: str, detected: dict, raw_response: dict,
) -> IdentificationScan:
    scan = IdentificationScan(
        user_id=user_id,
        image_url=image_url,
        raw_response=raw_response,
        detected_name=detected.get("detected_name"),
        detected_number=detected.get("detected_number"),
        detected_set=detected.get("detected_set"),
        detected_language=detected.get("detected_language"),
        detected_variant=detected.get("detected_variant"),
        detected_game_id=detected.get("detected_game_id"),
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)
    return scan


def add_identification_matches(
    db: Session, scan_id: int, matches: list[tuple[int, Optional[int], float, str]],
) -> None:
    """matches: list of (candidate_card_id, candidate_variant_id, confidence, match_method)."""
    for candidate_card_id, candidate_variant_id, confidence, match_method in matches:
        db.add(IdentificationMatch(
            scan_id=scan_id,
            candidate_card_id=candidate_card_id,
            candidate_variant_id=candidate_variant_id,
            confidence=confidence,
            match_method=match_method,
        ))
    db.commit()


def get_identification_scan(db: Session, user_id: int, scan_id: int) -> Optional[IdentificationScan]:
    return (
        db.query(IdentificationScan)
        .filter(IdentificationScan.id == scan_id, IdentificationScan.user_id == user_id)
        .first()
    )


def _normalize(s: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").strip().lower())


def _name_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def match_candidates(
    db: Session,
    detected_name: Optional[str],
    detected_number: Optional[str],
    detected_set: Optional[str],
    detected_game_slug: Optional[str] = None,
    limit: int = 5,
) -> list[tuple[TradingCard, Optional[int], float, str]]:
    """Weighted-tiers matching, same fuzzy-match style as crud.search_kiosk_series
    (difflib, already a stdlib dependency - no new library needed):

    Tier 1 - exact card_number match + name similarity >=0.85 (+ set
             similarity >=0.7 if a set was detected) -> confidence >=0.95
    Tier 2 - same as tier 1 but ignoring set (handles a misread set name)
             -> confidence 0.70-0.85
    Tier 2b - exact card_number match alone, when nothing cleared tier 1/2
             (name wasn't read at all, or didn't match well enough) ->
             confidence 0.45-0.60. Real gap this closes: a small vision
             model often reads a large printed number reliably while
             failing on smaller name/set text - without this tier, a
             successful number read with a failed name read produced zero
             candidates instead of "these cards all have that number."
    Tier 3 - name-only fuzzy match within the detected game (or across all
             games if none detected) -> floor 0.6, top `limit`

    Returns (card, variant_id, confidence, match_method) tuples, highest
    confidence first. Below-floor -> empty list, caller/UI should offer a
    manual-search fallback rather than force a guess."""
    game = get_game_by_slug(db, detected_game_slug) if detected_game_slug else None
    norm_name = _normalize(detected_name)
    norm_set = _normalize(detected_set)

    results: list[tuple[TradingCard, Optional[int], float, str]] = []
    number_matches: list[TradingCard] = []

    if detected_number:
        q = db.query(TradingCard).filter(TradingCard.card_number == detected_number)
        if game:
            q = q.filter(TradingCard.game_id == game.id)
        number_matches = q.all()
        for card in number_matches:
            name_sim = _name_similarity(norm_name, _normalize(card.name))
            if name_sim < 0.85:
                continue
            if norm_set:
                set_sim = _name_similarity(norm_set, _normalize(card.set_name))
                if set_sim >= 0.7:
                    results.append((card, None, min(0.99, 0.90 + name_sim * 0.09), "exact_number_name_set"))
                    continue
            results.append((card, None, 0.70 + name_sim * 0.15, "exact_number_name"))

        if not results and number_matches:
            # A single number-only match deserves more confidence than one
            # of several (more candidates = more ambiguity to resolve).
            confidence = 0.60 if len(number_matches) == 1 else 0.45
            results = [(card, None, confidence, "number_only") for card in number_matches[:limit]]

    if not results and norm_name:
        q = db.query(TradingCard)
        if game:
            q = q.filter(TradingCard.game_id == game.id)
        scored = []
        for card in q.all():
            sim = _name_similarity(norm_name, _normalize(card.name))
            if sim >= 0.6:
                scored.append((sim, card))
        scored.sort(key=lambda t: t[0], reverse=True)
        results = [(card, None, sim, "fuzzy_name") for sim, card in scored[:limit]]

    results.sort(key=lambda t: t[2], reverse=True)
    return results[:limit]


# --- Kiosk (customer-facing) ---
# Direct mirror of crud.py's comics kiosk section (_available_kiosk_items,
# get_kiosk_available_by_price, get_kiosk_available_signed,
# get_user_comics_by_ids, search_kiosk_series, get_kiosk_items_by_series) -
# same shape, adapted for cards. KioskFeaturedSet/get_fresh_featured_ids/
# set_featured_ids are already generic (keyed by a plain `section` string)
# and reused as-is from crud.py, just with new section names
# ("cards_todays_picks", "cards_graded").

def _available_kiosk_card_items(q) -> list[UserTradingCard]:
    # UserTradingCard.sales is a derived @property over .transactions, not a
    # real relationship - eager-load transactions (the actual relationship)
    # so the property doesn't trigger a lazy query per row.
    items = q.options(joinedload(UserTradingCard.transactions), joinedload(UserTradingCard.card)).all()
    return [uc for uc in items if (uc.count or 1) > len(uc.sales)]


def _kiosk_cards_sort_key(uc: UserTradingCard) -> tuple[str, str, str]:
    return (uc.card.name, uc.card.set_name or "", uc.card.card_number or "")


def _kiosk_cards_available_by_price(db: Session, threshold: float) -> list[UserTradingCard]:
    q = db.query(UserTradingCard).join(TradingCard).filter(
        or_(
            UserTradingCard.asking_price > threshold,
            and_(UserTradingCard.asking_price.is_(None), TradingCard.average_price > threshold),
        )
    )
    return _available_kiosk_card_items(q)


def get_kiosk_cards_available_by_price(db: Session, threshold: float, limit: int) -> list[UserTradingCard]:
    available = _kiosk_cards_available_by_price(db, threshold)
    return random.sample(available, min(limit, len(available)))


def get_all_kiosk_cards_available_by_price(db: Session, threshold: float) -> list[UserTradingCard]:
    """Unsampled - the full "Browse All" pool, not just a featured subset."""
    available = _kiosk_cards_available_by_price(db, threshold)
    return sorted(available, key=_kiosk_cards_sort_key)


def _kiosk_cards_graded(db: Session) -> list[UserTradingCard]:
    q = db.query(UserTradingCard).join(TradingCard).filter(UserTradingCard.grades.any())
    return _available_kiosk_card_items(q)


def get_kiosk_cards_graded(db: Session, limit: int) -> list[UserTradingCard]:
    available = _kiosk_cards_graded(db)
    return random.sample(available, min(limit, len(available)))


def get_all_kiosk_cards_graded(db: Session) -> list[UserTradingCard]:
    """Unsampled - the full "Browse All" pool, not just a featured subset."""
    available = _kiosk_cards_graded(db)
    return sorted(available, key=_kiosk_cards_sort_key)


def get_user_trading_cards_by_ids(db: Session, ids: list[int]) -> list[UserTradingCard]:
    if not ids:
        return []
    rows = (
        db.query(UserTradingCard)
        .join(TradingCard)
        .options(joinedload(UserTradingCard.transactions), joinedload(UserTradingCard.card))
        .filter(UserTradingCard.id.in_(ids))
        .all()
    )
    by_id = {uc.id: uc for uc in rows if (uc.count or 1) > len(uc.sales)}
    return [by_id[i] for i in ids if i in by_id]


def search_kiosk_cards(db: Session, query: str, limit: int = 10) -> list[dict]:
    available = _available_kiosk_card_items(db.query(UserTradingCard).join(TradingCard))
    counts: dict[str, int] = {}
    for uc in available:
        counts[uc.card.name] = counts.get(uc.card.name, 0) + 1

    normalized_query = re.sub(r"[^a-z0-9]", "", query.strip().lower())
    if not normalized_query:
        return []

    scored: list[tuple[float, str, int]] = []
    for name, count in counts.items():
        normalized_name = re.sub(r"[^a-z0-9]", "", name.lower())
        score = 1.0 if normalized_query in normalized_name else difflib.SequenceMatcher(
            None, normalized_query, normalized_name
        ).ratio()
        if score >= 0.5:
            scored.append((score, name, count))

    scored.sort(key=lambda t: t[0], reverse=True)
    return [{"name": name, "count": count} for _score, name, count in scored[:limit]]


def get_kiosk_cards_by_name(db: Session, card_name: str) -> list[UserTradingCard]:
    q = db.query(UserTradingCard).join(TradingCard).filter(TradingCard.name == card_name)
    available = _available_kiosk_card_items(q)

    def sort_key(uc: UserTradingCard) -> tuple[str, str]:
        return (uc.card.set_name or "", uc.card.card_number or "")

    return sorted(available, key=sort_key)
