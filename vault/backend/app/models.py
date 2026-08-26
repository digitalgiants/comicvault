from datetime import date, datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, JSON, String, Text, UniqueConstraint, Date
)
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    # Nullable - a Google-only account (see routes/users.py's /auth/google-login)
    # has no password at all, not just an unset one. auth.py's login route
    # guards against verifying a password against a None hash.
    password_hash = Column(String, nullable=True)
    # Nullable/unique - only set for accounts that have signed in with Google
    # at least once (either created that way, or a password account that later
    # links). Used to match a Google sign-in back to an existing account.
    email = Column(String, unique=True, index=True, nullable=True)
    is_admin = Column(Boolean, default=False)
    is_kiosk = Column(Boolean, default=False)
    # Seller (default, full-featured) vs. Collector (sales/pricing tools
    # hidden throughout the app) - chosen once at signup, see SignupPage.tsx.
    is_collector = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user_comics = relationship("UserComic", back_populates="user")
    csv_imports = relationship("CSVImport", back_populates="user")
    comics_added = relationship("Comic", back_populates="created_by_user")
    column_preferences = relationship("UserColumnPreference", back_populates="user")
    snapshots = relationship("CollectionSnapshot", back_populates="user")
    bug_reports = relationship("BugReport", back_populates="user")
    user_trading_cards = relationship("UserTradingCard", back_populates="user")


class Comic(Base):
    __tablename__ = "comics"

    id = Column(Integer, primary_key=True, index=True)
    upc = Column(String, unique=True, nullable=True, index=True)
    img = Column(String, nullable=True)
    # Resolved from owners' personal photos (see crud.recompute_comic_master_photo)
    # - takes priority over img wherever the comic's cover is displayed, without
    # discarding the original looked-up image if the photo is later removed.
    master_photo = Column(String, nullable=True)
    publisher = Column(String, index=True)
    series = Column(String, index=True, nullable=False)
    volume = Column(String, nullable=True)
    issue_number = Column(String, nullable=True, index=True)
    legacy_number = Column(String, nullable=True)
    cover_date = Column(Date, nullable=True)
    store_date = Column(Date, nullable=True)
    # True = newsstand edition, False/None = direct market (the common case).
    # Renamed+inverted from the old `direct` column - see migrate.py.
    newstand = Column(Boolean, nullable=True)
    print_run = Column(String, nullable=True)
    variant = Column(String, nullable=True)
    # The short cover designation (e.g. "A", "B", "1"), distinct from
    # `variant`'s free-text description (e.g. "Cover B - John Doe Variant").
    # No lookup provider currently supplies this - manual/CSV entry only.
    cover_letter = Column(String, nullable=True)
    cover_artist = Column(String, nullable=True)
    penciller = Column(String, nullable=True)
    inker = Column(String, nullable=True)
    writer = Column(String, nullable=True, index=True)
    average_price = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_by_user = relationship("User", back_populates="comics_added")
    user_comics = relationship("UserComic", back_populates="comic")


class UserComic(Base):
    __tablename__ = "user_comics"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    comic_id = Column(Integer, ForeignKey("comics.id"), nullable=False, index=True)
    count = Column(Integer, default=1)
    paid_price = Column(Float, nullable=True)
    asking_price = Column(Float, nullable=True)
    point_of_purchase = Column(String, nullable=True)
    buy_date = Column(DateTime, nullable=True)
    signed = Column(Boolean, default=False)
    remarked = Column(Boolean, default=False)
    condition = Column(String, nullable=True)
    personal_img = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    do_not_sell = Column(Boolean, nullable=False, default=False)
    # How many of `count` are held back and never counted as available for
    # sale (e.g. "sell all but one") - independent of do_not_sell, which
    # withholds all of them. See crud._available_kiosk_items and
    # availableCopies() in the frontend for how this factors into "available".
    reserve_count = Column(Integer, nullable=True, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="user_comics")
    comic = relationship("Comic", back_populates="user_comics")
    sales = relationship("Sale", back_populates="user_comic", cascade="all, delete-orphan", order_by="Sale.sell_date")


class Sale(Base):
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, index=True)
    user_comic_id = Column(Integer, ForeignKey("user_comics.id"), nullable=False, index=True)
    sell_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    sell_price = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user_comic = relationship("UserComic", back_populates="sales")


class CSVImport(Base):
    __tablename__ = "csv_imports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    total_rows = Column(Integer, default=0)
    successful_imports = Column(Integer, default=0)
    failed_rows = Column(Integer, default=0)
    error_log = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="csv_imports")


class CsvImportConflict(Base):
    """A single field where a CSV import row had a value that DIFFERED from
    what GCD reported for the same comic - never applied automatically,
    held here for the user to accept (apply GCD's value) or reject (keep
    what was already imported from the CSV) via the Upload page's
    persistent review queue. Blank CSV cells are filled from GCD directly
    at import time and never produce a row here - only genuine conflicts."""
    __tablename__ = "csv_import_conflicts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    csv_import_id = Column(Integer, ForeignKey("csv_imports.id"), nullable=True)
    comic_id = Column(Integer, ForeignKey("comics.id"), nullable=False, index=True)
    field_name = Column(String, nullable=False)
    csv_value = Column(String, nullable=True)
    gcd_value = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending")  # pending / accepted / rejected
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    user = relationship("User")
    comic = relationship("Comic")


class RejectedCoverImage(Base):
    """An image URL a user explicitly rejected as the wrong cover for a
    comic (via Find Image's picker, or the bulk backfill review screen) -
    excluded from future Find Image / backfill searches for that same
    comic so a rejected match doesn't keep resurfacing."""
    __tablename__ = "rejected_cover_images"

    id = Column(Integer, primary_key=True, index=True)
    comic_id = Column(Integer, ForeignKey("comics.id"), nullable=False, index=True)
    image_url = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    comic = relationship("Comic")

    __table_args__ = (UniqueConstraint("comic_id", "image_url", name="uq_rejected_cover_images"),)


class CollectionSnapshot(Base):
    __tablename__ = "collection_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    comic_count = Column(Integer, default=0)
    total_paid = Column(Float, default=0.0)
    total_value = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="snapshots")


class UserColumnPreference(Base):
    __tablename__ = "user_column_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    page = Column(String, nullable=False)  # 'collection' or 'sold'
    columns = Column(JSON, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "page", name="uq_user_page_prefs"),)

    user = relationship("User", back_populates="column_preferences")


class BugReport(Base):
    __tablename__ = "bug_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    text = Column(Text, nullable=False)
    comic_id = Column(Integer, ForeignKey("comics.id"), nullable=True)
    page_url = Column(String, nullable=True)
    resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="bug_reports")
    comic = relationship("Comic")


class KioskSignup(Base):
    __tablename__ = "kiosk_signups"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, nullable=False, index=True)
    phone = Column(String, nullable=True)
    notes = Column(Text, nullable=True)  # "Anything you looking for in particular?"
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class KioskSearchLog(Base):
    """One row per kiosk title search (comics or trading cards) - lets an
    admin see what customers are actually looking for, including titles
    the shop doesn't carry."""
    __tablename__ = "kiosk_search_logs"

    id = Column(Integer, primary_key=True, index=True)
    query = Column(String, nullable=False, index=True)
    section = Column(String, nullable=False)  # "comics" | "cards"
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class KioskFeaturedSet(Base):
    """Cached random selection for a kiosk section, regenerated on an
    admin-configurable interval - see KioskSettings."""
    __tablename__ = "kiosk_featured_sets"

    section = Column(String, primary_key=True)
    item_ids = Column(JSON, default=list)
    generated_at = Column(DateTime, default=datetime.utcnow)


class KioskSettings(Base):
    """Single-row admin-configurable kiosk settings - "Today's Picks" price
    thresholds and per-section featured-set refresh intervals. Always exactly
    one row; crud.get_kiosk_settings creates it with defaults on first access."""
    __tablename__ = "kiosk_settings"

    id = Column(Integer, primary_key=True)
    comics_price_threshold = Column(Float, nullable=False, default=100.0)
    cards_price_threshold = Column(Float, nullable=False, default=100.0)
    todays_picks_refresh_minutes = Column(Integer, nullable=False, default=1440)
    signed_refresh_minutes = Column(Integer, nullable=False, default=1440)
    cards_todays_picks_refresh_minutes = Column(Integer, nullable=False, default=1440)
    cards_graded_refresh_minutes = Column(Integer, nullable=False, default=1440)
    featured_limit = Column(Integer, nullable=False, default=25)


class ExternalSeriesSync(Base):
    """Tracks whether a provider's full issue list has been paginated into
    ExternalIssueCache, so repeat visits to a series don't re-hit the
    rate-limited external API."""
    __tablename__ = "external_series_syncs"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, nullable=False, index=True)
    provider_series_id = Column(String, nullable=False, index=True)
    series_name = Column(String, nullable=True)
    known_issue_count = Column(Integer, nullable=True)
    synced_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("provider", "provider_series_id", name="uq_series_sync_provider_id"),
    )


class ExternalIssueCache(Base):
    """Permanent local mirror of an external provider's issue data. Summary
    fields (number/cover_date/image) are populated when a series is paginated;
    detail fields are populated lazily the first time a specific issue's full
    fields are fetched for adding to a collection."""
    __tablename__ = "external_issue_cache"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, nullable=False, index=True)
    provider_issue_id = Column(String, nullable=False, index=True)
    # Nullable: a row created purely from an issue-fields lookup (rather than
    # from paginating its series) may not have this on hand.
    provider_series_id = Column(String, nullable=True, index=True)

    number = Column(String, nullable=True)
    cover_date = Column(String, nullable=True)
    image = Column(String, nullable=True)

    fields_synced = Column(Boolean, default=False)
    publisher = Column(String, nullable=True)
    series = Column(String, nullable=True)
    volume = Column(String, nullable=True)
    store_date = Column(String, nullable=True)
    print_run = Column(String, nullable=True)
    variant = Column(String, nullable=True)
    cover_letter = Column(String, nullable=True)
    newstand = Column(Boolean, nullable=True)
    writer = Column(String, nullable=True)
    penciller = Column(String, nullable=True)
    inker = Column(String, nullable=True)
    cover_artist = Column(String, nullable=True)
    average_price = Column(Float, nullable=True)
    upc = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("provider", "provider_issue_id", name="uq_issue_cache_provider_id"),
    )


class ExternalSeriesSearchLog(Base):
    """Tracks when a (provider, normalized query) title search was last run,
    so repeat searches serve from ExternalSeriesSearchCache instead of
    re-hitting the provider. Unlike issue data, series search results are
    given a TTL (not permanent) - new series get published/indexed over time,
    and there's no cheap way to detect that the way there is for issue
    counts on an already-known series."""
    __tablename__ = "external_series_search_logs"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, nullable=False, index=True)
    query = Column(String, nullable=False, index=True)
    searched_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("provider", "query", name="uq_series_search_log_provider_query"),
    )


class ExternalSeriesSearchCache(Base):
    """Cached results of a series-title search, keyed by normalized query text."""
    __tablename__ = "external_series_search_cache"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, nullable=False, index=True)
    query = Column(String, nullable=False, index=True)
    provider_series_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    publisher = Column(String, nullable=True)
    start_year = Column(Integer, nullable=True)
    issue_count = Column(Integer, nullable=True)
    image = Column(String, nullable=True)


# --- Trading cards (any TCG - Pokemon, Magic, One Piece, etc.) ---
# Parallel structure to Comic/UserComic/Sale above, not a shared schema -
# card-specific stats vary too much per game to unify with comics' creator
# credits. See feature-requests/tcg_card_scanner_build_prompt.md.

class CardGame(Base):
    """A TCG (Pokemon, Magic, One Piece, ...), synced from apitcg.com's
    /api/tcgs list via the tcg-scraper service."""
    __tablename__ = "card_games"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    logo_image_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    series = relationship("CardSeries", back_populates="game")
    sets = relationship("CardSet", back_populates="game")
    cards = relationship("TradingCard", back_populates="game")


class CardSeries(Base):
    __tablename__ = "card_series"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("card_games.id"), nullable=False, index=True)
    external_id = Column(String, nullable=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("game_id", "name", name="uq_card_series_game_name"),)

    game = relationship("CardGame", back_populates="series")
    sets = relationship("CardSet", back_populates="series")


class CardSet(Base):
    __tablename__ = "card_sets"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("card_games.id"), nullable=False, index=True)
    series_id = Column(Integer, ForeignKey("card_series.id"), nullable=True)
    external_id = Column(String, nullable=True)
    name = Column(String, nullable=False)
    set_code = Column(String, nullable=True)
    printed_total = Column(Integer, nullable=True)
    total_cards = Column(Integer, nullable=True)
    release_date = Column(Date, nullable=True)
    symbol_image_url = Column(String, nullable=True)
    logo_image_url = Column(String, nullable=True)
    language = Column(String, nullable=False, default="English")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("game_id", "name", "language", name="uq_card_sets_game_name_lang"),)

    game = relationship("CardGame", back_populates="sets")
    series = relationship("CardSeries", back_populates="sets")
    cards = relationship("TradingCard", back_populates="set")


class TradingCard(Base):
    """Shared catalog entry - one row per distinct card/printing, mirrors
    Comic's role. created_by_user_id is set when a card is added manually
    rather than synced from apitcg.com."""
    __tablename__ = "trading_cards"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("card_games.id"), nullable=False, index=True)
    set_id = Column(Integer, ForeignKey("card_sets.id"), nullable=False, index=True)
    name = Column(String, nullable=False, index=True)
    card_number = Column(String, nullable=True, index=True)
    code = Column(String, nullable=True)
    rarity = Column(String, nullable=True)
    language = Column(String, nullable=False, default="English")
    description = Column(Text, nullable=True)
    # Per-game stat bag (HP/attacks/Power/Color for Pokemon, mana cost/type
    # line for Magic, etc.) - mirrors apitcg.com's own dynamic `attributes`
    # field. Deliberately not fixed columns - they don't generalize across games.
    attributes = Column(JSON, nullable=True)
    image_small = Column(String, nullable=True)
    image_medium = Column(String, nullable=True)
    image_large = Column(String, nullable=True)
    # Resolved from owners' personal photos, same role as Comic.master_photo.
    master_photo = Column(String, nullable=True)
    average_price = Column(Float, nullable=True)
    release_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint("set_id", "card_number", "language", name="uq_trading_cards_set_number_lang"),
    )

    game = relationship("CardGame", back_populates="cards")
    set = relationship("CardSet", back_populates="cards")

    @property
    def game_slug(self) -> "str | None":
        return self.game.slug if self.game else None

    @property
    def game_name(self) -> "str | None":
        return self.game.name if self.game else None

    @property
    def set_name(self) -> "str | None":
        return self.set.name if self.set else None
    variants = relationship("TradingCardVariant", back_populates="card", cascade="all, delete-orphan")
    external_ids = relationship("TradingCardExternalId", back_populates="card", cascade="all, delete-orphan")
    images = relationship("TradingCardImage", back_populates="card", cascade="all, delete-orphan")
    prices = relationship("TradingCardPrice", back_populates="card", cascade="all, delete-orphan")
    price_history = relationship("TradingCardPriceHistory", back_populates="card", cascade="all, delete-orphan")
    user_trading_cards = relationship("UserTradingCard", back_populates="card")


class TradingCardVariant(Base):
    __tablename__ = "trading_card_variants"

    id = Column(Integer, primary_key=True, index=True)
    card_id = Column(Integer, ForeignKey("trading_cards.id"), nullable=False, index=True)
    variant_type = Column(String, nullable=False)
    finish = Column(String, nullable=True)
    foil_pattern = Column(String, nullable=True)
    parallel_type = Column(String, nullable=True)
    stamp = Column(String, nullable=True)
    stamped_text = Column(String, nullable=True)
    alternate_art = Column(Boolean, default=False)
    special_print = Column(Boolean, default=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "card_id", "variant_type", "finish", "foil_pattern",
            "parallel_type", "stamp", "stamped_text", name="uq_trading_card_variants",
        ),
    )

    card = relationship("TradingCard", back_populates="variants")


class TradingCardExternalId(Base):
    """Natural key used to dedup/reconcile during apitcg.com sync - same
    role as ExternalIssueCache's (provider, provider_issue_id) pairing."""
    __tablename__ = "trading_card_external_ids"

    id = Column(Integer, primary_key=True, index=True)
    card_id = Column(Integer, ForeignKey("trading_cards.id"), nullable=False, index=True)
    source = Column(String, nullable=False)
    external_id = Column(String, nullable=False)
    url = Column(String, nullable=True)

    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_trading_card_external_ids"),)

    card = relationship("TradingCard", back_populates="external_ids")


class TradingCardImage(Base):
    __tablename__ = "trading_card_images"

    id = Column(Integer, primary_key=True, index=True)
    card_id = Column(Integer, ForeignKey("trading_cards.id"), nullable=False, index=True)
    variant_id = Column(Integer, ForeignKey("trading_card_variants.id"), nullable=True)
    image_type = Column(String, nullable=False)  # front / back / reference / variant / scan
    image_url = Column(String, nullable=False)
    image_hash = Column(String, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    card = relationship("TradingCard", back_populates="images")


class TradingCardPrice(Base):
    """Current/latest market price snapshot per source, mirrors apitcg's
    `markets` field on a product."""
    __tablename__ = "trading_card_prices"

    id = Column(Integer, primary_key=True, index=True)
    card_id = Column(Integer, ForeignKey("trading_cards.id"), nullable=False, index=True)
    variant_id = Column(Integer, ForeignKey("trading_card_variants.id"), nullable=True)
    source = Column(String, nullable=False)
    price_type = Column(String, nullable=False)
    condition = Column(String, nullable=True)
    grader = Column(String, nullable=True)
    grade = Column(String, nullable=True)
    price = Column(Float, nullable=False)
    currency = Column(String, nullable=False, default="USD")
    observed_at = Column(DateTime, default=datetime.utcnow)

    card = relationship("TradingCard", back_populates="prices")


class TradingCardPriceHistory(Base):
    """Time series mirroring apitcg's /history-prices/{productId} endpoint."""
    __tablename__ = "trading_card_price_history"

    id = Column(Integer, primary_key=True, index=True)
    card_id = Column(Integer, ForeignKey("trading_cards.id"), nullable=False, index=True)
    variant_id = Column(Integer, ForeignKey("trading_card_variants.id"), nullable=True)
    source = Column(String, nullable=False)
    condition = Column(String, nullable=True)
    grader = Column(String, nullable=True)
    grade = Column(String, nullable=True)
    price = Column(Float, nullable=False)
    currency = Column(String, nullable=False, default="USD")
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)

    card = relationship("TradingCard", back_populates="price_history")


class StorageLocation(Base):
    """Not used by any route/UI yet (phase 2) - created now so
    UserTradingCard.storage_location_id has a clean FK target from day one."""
    __tablename__ = "storage_locations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    location_type = Column(String, nullable=True)
    parent_location_id = Column(Integer, ForeignKey("storage_locations.id"), nullable=True)
    description = Column(Text, nullable=True)

    __table_args__ = (UniqueConstraint("name", "parent_location_id", name="uq_storage_locations_name_parent"),)


class UserTradingCard(Base):
    """Personal ownership - mirrors UserComic exactly."""
    __tablename__ = "user_trading_cards"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    card_id = Column(Integer, ForeignKey("trading_cards.id"), nullable=False, index=True)
    variant_id = Column(Integer, ForeignKey("trading_card_variants.id"), nullable=True)
    count = Column(Integer, default=1)
    condition = Column(String, nullable=False, default="Unknown")
    language = Column(String, nullable=True)
    storage_location_id = Column(Integer, ForeignKey("storage_locations.id"), nullable=True)
    storage_position = Column(String, nullable=True)
    point_of_purchase = Column(String, nullable=True)
    buy_date = Column(DateTime, nullable=True)
    paid_price = Column(Float, nullable=True)
    asking_price = Column(Float, nullable=True)
    for_sale = Column(Boolean, default=False)
    personal_img = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    do_not_sell = Column(Boolean, nullable=False, default=False)
    reserve_count = Column(Integer, nullable=True, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="user_trading_cards")
    card = relationship("TradingCard", back_populates="user_trading_cards")
    grades = relationship("CardGrade", back_populates="user_trading_card", cascade="all, delete-orphan")
    transactions = relationship(
        "CardTransaction", back_populates="user_trading_card",
        cascade="all, delete-orphan", order_by="CardTransaction.transaction_date",
    )

    @property
    def sales(self) -> list["CardTransaction"]:
        """Derived view, not a stored relationship - "sales" for the API/UI
        are just transactions filtered to type 'Sale', mirroring UserComic.sales'
        shape without a second relationship mapping for one string value."""
        return [t for t in self.transactions if t.transaction_type == "Sale"]


class CardGrade(Base):
    """A single grading submission for a physical card - a card can be
    regraded/resubmitted, so this is 1-to-many off UserTradingCard rather
    than flat graded/grading_company/grade columns."""
    __tablename__ = "card_grades"

    id = Column(Integer, primary_key=True, index=True)
    user_trading_card_id = Column(Integer, ForeignKey("user_trading_cards.id"), nullable=False, index=True)
    grader = Column(String, nullable=False)  # PSA / BGS / SGC / CGC / ...
    grade = Column(String, nullable=False)
    certification_number = Column(String, nullable=True)
    graded_date = Column(Date, nullable=True)
    label_type = Column(String, nullable=True)
    population = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)

    __table_args__ = (UniqueConstraint("grader", "certification_number", name="uq_card_grades_grader_cert"),)

    user_trading_card = relationship("UserTradingCard", back_populates="grades")


class CardTransaction(Base):
    """Purchase/Sale/Trade/Gift ledger for a card - richer than comics'
    paid_price+Sale split since it can represent trades/gifts. transaction_type
    is a plain string (Purchase/Sale/Trade/Gift/Other), not a Postgres ENUM,
    same reasoning as everywhere else in this schema. SET NULL on delete so
    transaction history survives even if the collection entry is removed."""
    __tablename__ = "card_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_trading_card_id = Column(
        Integer, ForeignKey("user_trading_cards.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    transaction_type = Column(String, nullable=False)
    transaction_date = Column(Date, nullable=False, default=date.today)
    source = Column(String, nullable=True)
    counterparty = Column(String, nullable=True)
    price = Column(Float, nullable=True)
    shipping = Column(Float, default=0)
    tax = Column(Float, default=0)
    fees = Column(Float, default=0)
    total_cost = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user_trading_card = relationship("UserTradingCard", back_populates="transactions")


class IdentificationScan(Base):
    """A single photo-identification attempt. raw_response is the vision
    model's full structured output - never discarded, so identification
    logic can improve later without losing historical scans."""
    __tablename__ = "identification_scans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    image_url = Column(String, nullable=False)
    processed_image_url = Column(String, nullable=True)
    raw_response = Column(JSON, nullable=True)
    detected_name = Column(String, nullable=True, index=True)
    detected_number = Column(String, nullable=True, index=True)
    detected_set = Column(String, nullable=True)
    detected_language = Column(String, nullable=True)
    detected_variant = Column(String, nullable=True)
    detected_game_id = Column(Integer, ForeignKey("card_games.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class IdentificationMatch(Base):
    """A candidate card the matcher proposed for a scan, with the
    confidence/method that produced it - lets the confirmation UI show
    multiple options rather than forcing a single guess."""
    __tablename__ = "identification_matches"

    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("identification_scans.id"), nullable=False, index=True)
    candidate_card_id = Column(Integer, ForeignKey("trading_cards.id"), nullable=False)
    candidate_variant_id = Column(Integer, ForeignKey("trading_card_variants.id"), nullable=True)
    confidence = Column(Float, nullable=True)
    match_method = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("scan_id", "candidate_card_id", "candidate_variant_id", name="uq_identification_matches"),
    )
