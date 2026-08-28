from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# --- Auth ---

class UserCreate(BaseModel):
    username: str
    password: str
    is_collector: bool = False


class UserLogin(BaseModel):
    username: str
    password: str


class GoogleLoginRequest(BaseModel):
    # The ID token JWT string Google Identity Services hands back to the
    # frontend - verified server-side in routes/users.py, never trusted
    # as-is (see google_auth.verify_google_id_token).
    credential: str


class UserOut(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    is_admin: bool
    is_kiosk: bool
    is_collector: bool
    has_seen_tour: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Comics ---

class ComicBase(BaseModel):
    publisher: Optional[str] = None
    series: str
    volume: Optional[str] = None
    issue_number: Optional[str] = None
    legacy_number: Optional[str] = None
    cover_date: Optional[date] = None
    store_date: Optional[date] = None
    print_run: Optional[str] = None
    variant: Optional[str] = None
    cover_letter: Optional[str] = None
    newstand: Optional[bool] = None
    writer: Optional[str] = None
    penciller: Optional[str] = None
    inker: Optional[str] = None
    cover_artist: Optional[str] = None
    average_price: Optional[float] = None
    upc: Optional[str] = None
    img: Optional[str] = None


class ComicCreate(ComicBase):
    pass


class ComicUpdate(BaseModel):
    average_price: Optional[float] = None
    publisher: Optional[str] = None
    series: Optional[str] = None
    volume: Optional[str] = None
    issue_number: Optional[str] = None
    legacy_number: Optional[str] = None
    cover_date: Optional[date] = None
    store_date: Optional[date] = None
    print_run: Optional[str] = None
    variant: Optional[str] = None
    cover_letter: Optional[str] = None
    newstand: Optional[bool] = None
    writer: Optional[str] = None
    penciller: Optional[str] = None
    inker: Optional[str] = None
    cover_artist: Optional[str] = None
    upc: Optional[str] = None
    img: Optional[str] = None


class ComicMetadataUpdate(BaseModel):
    """Shared Comic fields any logged-in user may correct, as opposed to the
    admin-only ComicUpdate which allows editing the full record."""
    upc: Optional[str] = None
    cover_artist: Optional[str] = None
    cover_letter: Optional[str] = None
    volume: Optional[str] = None
    publisher: Optional[str] = None
    img: Optional[str] = None


class ComicOut(ComicBase):
    id: int
    created_at: datetime
    master_photo: Optional[str] = None

    class Config:
        from_attributes = True


# --- Sales ---

class SaleOut(BaseModel):
    id: int
    user_comic_id: int
    sell_date: datetime
    sell_price: Optional[float] = None
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SaleCreate(BaseModel):
    sell_date: datetime
    sell_price: Optional[float] = None
    notes: Optional[str] = None


class SaleUpdate(BaseModel):
    sell_price: Optional[float] = None


class SaleWithComicOut(BaseModel):
    id: int
    user_comic_id: int
    sell_date: datetime
    sell_price: Optional[float] = None
    notes: Optional[str] = None
    created_at: datetime
    comic: ComicOut

    class Config:
        from_attributes = True


# --- UserComics ---

class UserComicBase(BaseModel):
    count: Optional[int] = 1
    paid_price: Optional[float] = None
    asking_price: Optional[float] = None
    point_of_purchase: Optional[str] = None
    buy_date: Optional[datetime] = None
    signed: Optional[bool] = False
    remarked: Optional[bool] = False
    condition: Optional[str] = None
    personal_img: Optional[str] = None
    notes: Optional[str] = None
    do_not_sell: Optional[bool] = False
    reserve_count: Optional[int] = 0


class UserComicCreate(UserComicBase):
    comic_id: int


class UserComicUpdate(BaseModel):
    count: Optional[int] = None
    paid_price: Optional[float] = None
    asking_price: Optional[float] = None
    point_of_purchase: Optional[str] = None
    buy_date: Optional[datetime] = None
    signed: Optional[bool] = None
    remarked: Optional[bool] = None
    condition: Optional[str] = None
    personal_img: Optional[str] = None
    notes: Optional[str] = None
    do_not_sell: Optional[bool] = None
    reserve_count: Optional[int] = None


class BulkUpdateItem(BaseModel):
    id: int
    update: UserComicUpdate


class BulkUpdateRequest(BaseModel):
    updates: list[BulkUpdateItem]


class UserComicOut(UserComicBase):
    id: int
    user_id: int
    comic_id: int
    comic: ComicOut
    created_at: datetime
    sales: list[SaleOut] = []

    class Config:
        from_attributes = True


class SeriesGroupOut(BaseModel):
    series: str
    publisher: Optional[str] = None
    issue_count: int
    cover_img: Optional[str] = None
    cover_comic_id: int
    cover_issue_number: Optional[str] = None


# --- Admin: publisher naming-consistency report (see app.gcd_lookup) ---

class PublisherMismatchOut(BaseModel):
    local_publisher: str
    comic_count: int
    suggested_publisher: Optional[str] = None


class PublisherMergeItem(BaseModel):
    local_publisher: str
    target_publisher: str


class PublisherMergeRequest(BaseModel):
    updates: list[PublisherMergeItem]


class PublisherMergeSkip(BaseModel):
    local_publisher: str
    reason: str


class PublisherMergeResult(BaseModel):
    merged_comics: int
    skipped: list[PublisherMergeSkip]


# --- Admin: malformed-UPC report (see app.gcd_lookup._clean_barcode_digits
# and app.crud.get_malformed_upc_comics) ---

class UpcIssueOut(BaseModel):
    comic_id: int
    series: str
    issue_number: Optional[str] = None
    publisher: Optional[str] = None
    upc: str
    suggested_upc: Optional[str] = None


class LegacyNumberIssueOut(BaseModel):
    comic_id: int
    series: str
    issue_number: str
    publisher: Optional[str] = None
    suggested_issue_number: str
    suggested_legacy_number: str


# --- Admin: ComicVine cover-image sync (see app.external.comicvine) ---

class ComicVineSyncRequest(BaseModel):
    names: list[str]


class ComicVineSeriesSyncResult(BaseModel):
    query: str
    status: str  # "synced" | "not_found"
    matched_series: Optional[str] = None
    publisher: Optional[str] = None
    total_issues: Optional[int] = None
    issues_with_image: Optional[int] = None
    created: Optional[int] = None
    images_filled: Optional[int] = None
    skipped: Optional[int] = None


class ComicVineSyncResponse(BaseModel):
    results: list[ComicVineSeriesSyncResult]
    rate_limited: bool = False


# --- Collection: bulk-edit publisher for a user's own selected comics
# (see CollectionPage.tsx's BulkEditModal) - scoped to one user's selection,
# as opposed to the admin report above which sweeps the whole catalog. ---

class PublisherBulkEditRequest(BaseModel):
    uc_ids: list[int]
    publisher: str


class PublisherBulkSkip(BaseModel):
    comic_id: int
    reason: str


class PublisherBulkEditResult(BaseModel):
    updated_comics: int
    skipped: list[PublisherBulkSkip]


class PublisherSuggestRequest(BaseModel):
    uc_ids: list[int]


class PublisherSuggestResult(BaseModel):
    # "empty" (no valid selection) | "mixed" (selected comics don't share
    # one current publisher) | "no_suggestion" | "already_correct" | "suggestion"
    status: str
    publisher: Optional[str] = None


# --- Scan (barcode lookup) ---

class ScanAddRequest(BaseModel):
    comic: ComicCreate
    user_comic: UserComicBase


# --- Series search (Metron + ComicVine, by title) ---

class ExternalSeriesResult(BaseModel):
    provider: str
    provider_series_id: str
    name: str
    publisher: Optional[str] = None
    start_year: Optional[int] = None
    issue_count: Optional[int] = None
    image: Optional[str] = None


class ExternalSeriesSearchResult(BaseModel):
    results: list[ExternalSeriesResult]
    warnings: list[str] = []
    has_more: bool = False


class ImageCandidateOut(BaseModel):
    provider: str
    series_name: str
    image: str


class BackfillImageResult(BaseModel):
    status: str  # "found" | "already_has_image" | "not_found"
    image: Optional[str] = None


class RejectImageRequest(BaseModel):
    comic_id: int
    image: str


class UpcLookupResult(BaseModel):
    upc: Optional[str] = None


class ExternalIssueSummary(BaseModel):
    provider: str
    provider_issue_id: str
    number: Optional[str] = None
    legacy_number: Optional[str] = None
    cover_date: Optional[str] = None
    image: Optional[str] = None


# --- CSV Import ---

class CSVImportResult(BaseModel):
    success: bool
    filename: str
    total_rows: int
    imported: int
    failed: int
    new_comics_added_to_db: int
    existing_comics_linked: int
    sales_recorded: int
    errors: list[dict[str, Any]]
    declined: list[dict[str, Any]] = []
    conflicts_queued: int = 0


class CSVImportConflictOut(BaseModel):
    id: int
    comic_id: int
    comic_series: str
    comic_issue_number: Optional[str] = None
    field_name: str
    csv_value: Optional[str] = None
    gcd_value: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# --- Admin ---

class AdminUserOut(UserOut):
    csv_imports: list[Any] = []

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    is_admin: Optional[bool] = None
    is_kiosk: Optional[bool] = None


# --- Search ---

class ComicSearchParams(BaseModel):
    series: Optional[str] = None
    publisher: Optional[str] = None
    writer: Optional[str] = None
    volume: Optional[str] = None
    issue_number: Optional[str] = None
    variant: Optional[str] = None


# --- Column Preferences ---

class ColumnPreferenceOut(BaseModel):
    page: str
    columns: dict[str, bool]

    class Config:
        from_attributes = True


class ColumnPreferenceUpdate(BaseModel):
    columns: dict[str, bool]


# --- Collection Snapshots ---

class SnapshotOut(BaseModel):
    date: str
    comic_count: int
    total_paid: float
    total_value: float

    class Config:
        from_attributes = True


# --- Bug Reports ---

class BugReportCreate(BaseModel):
    text: str
    comic_id: Optional[int] = None
    page_url: Optional[str] = None


class BugReportOut(BaseModel):
    id: int
    text: str
    comic_id: Optional[int] = None
    page_url: Optional[str] = None
    resolved: bool
    created_at: datetime
    user_username: str
    comic_name: Optional[str] = None

    class Config:
        from_attributes = True


# --- Kiosk ---

class KioskSignupCreate(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    notes: Optional[str] = None


class KioskSignupOut(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class KioskSignupUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None


class KioskSearchLogOut(BaseModel):
    id: int
    query: str
    section: str
    created_at: datetime

    class Config:
        from_attributes = True


class KioskCardOut(BaseModel):
    """Customer-facing view of a pooled available comic - excludes cost/margin
    fields (paid_price, point_of_purchase, notes) that aren't the public's
    business, and no price shown to customers, same as KioskTradingCardOut -
    Today's Picks is filtered by price threshold server-side, it just
    doesn't display it."""
    id: int
    series: str
    volume: Optional[str] = None
    issue_number: Optional[str] = None
    legacy_number: Optional[str] = None
    cover_date: Optional[date] = None
    publisher: Optional[str] = None
    variant: Optional[str] = None
    cover_letter: Optional[str] = None
    img: Optional[str] = None
    cover_artist: Optional[str] = None
    penciller: Optional[str] = None
    inker: Optional[str] = None
    writer: Optional[str] = None
    newstand: Optional[bool] = None
    print_run: Optional[str] = None
    signed: bool = False
    remarked: bool = False
    condition: Optional[str] = None
    available: int = 0


class KioskTradingCardOut(BaseModel):
    """Customer-facing view of a pooled available card - mirrors
    KioskCardOut's role for comics, but deliberately more minimal: no
    grade/condition or price shown to customers, even for the Graded Cards
    section (that section is filtered by having a grade on file, it just
    doesn't display it) or Today's Picks (filtered by price threshold
    server-side, same story)."""
    id: int
    name: str
    game_name: Optional[str] = None
    set_name: Optional[str] = None
    card_number: Optional[str] = None
    rarity: Optional[str] = None
    img: Optional[str] = None
    available: int = 0


class SeriesSearchResult(BaseModel):
    name: str
    count: int


class KioskSettingsOut(BaseModel):
    comics_price_threshold: float
    cards_price_threshold: float
    todays_picks_refresh_minutes: int
    signed_refresh_minutes: int
    cards_todays_picks_refresh_minutes: int
    cards_graded_refresh_minutes: int
    featured_limit: int

    class Config:
        from_attributes = True


class KioskSettingsUpdate(BaseModel):
    comics_price_threshold: Optional[float] = Field(default=None, ge=0)
    cards_price_threshold: Optional[float] = Field(default=None, ge=0)
    todays_picks_refresh_minutes: Optional[int] = Field(default=None, ge=10, le=1440)
    signed_refresh_minutes: Optional[int] = Field(default=None, ge=10, le=1440)
    cards_todays_picks_refresh_minutes: Optional[int] = Field(default=None, ge=10, le=1440)
    cards_graded_refresh_minutes: Optional[int] = Field(default=None, ge=10, le=1440)
    featured_limit: Optional[int] = Field(default=None, ge=1, le=200)


# --- Trading cards (parallel to Comics above - see app/models.py's
# "Trading cards" section for why this isn't a shared schema) ---

class CardGameOut(BaseModel):
    id: int
    slug: str
    name: str
    logo_image_url: Optional[str] = None

    class Config:
        from_attributes = True


class CardSetGroupOut(BaseModel):
    set_id: int
    set_name: str
    game_name: Optional[str] = None
    game_slug: Optional[str] = None
    card_count: int
    cover_img: Optional[str] = None


class CardSetOut(BaseModel):
    id: int
    game_id: int
    series_id: Optional[int] = None
    external_id: Optional[str] = None
    name: str
    set_code: Optional[str] = None
    release_date: Optional[date] = None
    printed_total: Optional[int] = None
    total_cards: Optional[int] = None
    language: str

    class Config:
        from_attributes = True


class TradingCardBase(BaseModel):
    game_id: int
    set_id: int
    name: str
    card_number: Optional[str] = None
    code: Optional[str] = None
    rarity: Optional[str] = None
    language: Optional[str] = "English"
    description: Optional[str] = None
    attributes: Optional[dict] = None
    image_small: Optional[str] = None
    image_medium: Optional[str] = None
    image_large: Optional[str] = None
    release_date: Optional[date] = None
    average_price: Optional[float] = None


class TradingCardCreate(TradingCardBase):
    pass


class TradingCardUpdate(BaseModel):
    """Admin-only partial update, mirrors ComicUpdate's role."""
    name: Optional[str] = None
    card_number: Optional[str] = None
    code: Optional[str] = None
    rarity: Optional[str] = None
    language: Optional[str] = None
    description: Optional[str] = None
    attributes: Optional[dict] = None
    image_small: Optional[str] = None
    image_medium: Optional[str] = None
    image_large: Optional[str] = None
    release_date: Optional[date] = None
    average_price: Optional[float] = None


class TradingCardOut(TradingCardBase):
    id: int
    created_at: datetime
    master_photo: Optional[str] = None
    # Derived from the game/set relationships (see TradingCard properties in
    # models.py) purely so the frontend table doesn't need a separate
    # id->name lookup for every row.
    game_slug: Optional[str] = None
    game_name: Optional[str] = None
    set_name: Optional[str] = None

    class Config:
        from_attributes = True


class CardTransactionOut(BaseModel):
    id: int
    user_trading_card_id: Optional[int] = None
    transaction_type: str
    transaction_date: date
    source: Optional[str] = None
    counterparty: Optional[str] = None
    price: Optional[float] = None
    shipping: Optional[float] = None
    tax: Optional[float] = None
    fees: Optional[float] = None
    total_cost: Optional[float] = None
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CardSaleCreate(BaseModel):
    """Input for recording a sale specifically - a Purchase/Trade/Gift
    transaction can be added directly via CardTransaction if ever needed,
    but "sales" is the only transaction type with dedicated UI/API for v1."""
    transaction_date: date
    price: Optional[float] = None
    notes: Optional[str] = None


class CardSaleUpdate(BaseModel):
    price: Optional[float] = None


class UserTradingCardBase(BaseModel):
    count: Optional[int] = 1
    condition: Optional[str] = "Unknown"
    language: Optional[str] = None
    point_of_purchase: Optional[str] = None
    buy_date: Optional[datetime] = None
    paid_price: Optional[float] = None
    asking_price: Optional[float] = None
    for_sale: Optional[bool] = False
    personal_img: Optional[str] = None
    notes: Optional[str] = None
    do_not_sell: Optional[bool] = False
    reserve_count: Optional[int] = 0


class UserTradingCardCreate(UserTradingCardBase):
    card_id: int
    variant_id: Optional[int] = None


class UserTradingCardUpdate(BaseModel):
    count: Optional[int] = None
    condition: Optional[str] = None
    language: Optional[str] = None
    point_of_purchase: Optional[str] = None
    buy_date: Optional[datetime] = None
    paid_price: Optional[float] = None
    asking_price: Optional[float] = None
    for_sale: Optional[bool] = None
    personal_img: Optional[str] = None
    notes: Optional[str] = None
    do_not_sell: Optional[bool] = None
    reserve_count: Optional[int] = None


class CardBulkUpdateItem(BaseModel):
    id: int
    update: UserTradingCardUpdate


class CardBulkUpdateRequest(BaseModel):
    updates: list[CardBulkUpdateItem]


class UserTradingCardOut(UserTradingCardBase):
    id: int
    user_id: int
    card_id: int
    card: TradingCardOut
    created_at: datetime
    sales: list[CardTransactionOut] = []

    class Config:
        from_attributes = True


# --- Card identification (scan pipeline) ---

class ScanCandidateOut(BaseModel):
    card: TradingCardOut
    variant_id: Optional[int] = None
    confidence: float
    match_method: str


class IdentifyScanResponse(BaseModel):
    scan_id: int
    image_url: str
    detected_name: Optional[str] = None
    detected_number: Optional[str] = None
    detected_set: Optional[str] = None
    detected_language: Optional[str] = None
    detected_variant: Optional[str] = None
    candidates: list[ScanCandidateOut] = []


class CardScanConfirmRequest(BaseModel):
    """Only an existing catalog card can be confirmed onto - creating a new
    catalog entry stays admin-only (see /admin/cards), consistent with how
    the rest of the trading-card feature draws that line. If a scan matches
    nothing, the UI's "none of these" path reuses the same manual-search
    flow as the regular Add Card modal rather than a separate creation path."""
    candidate_card_id: int
    variant_id: Optional[int] = None
    user_trading_card: UserTradingCardBase = UserTradingCardBase()
