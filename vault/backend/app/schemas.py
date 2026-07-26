from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel


# --- Auth ---

class UserCreate(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    is_admin: bool
    is_kiosk: bool
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
    cover_date: Optional[date] = None
    store_date: Optional[date] = None
    print_run: Optional[str] = None
    variant: Optional[str] = None
    direct: Optional[bool] = None
    writer: Optional[str] = None
    artist: Optional[str] = None
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
    cover_date: Optional[date] = None
    store_date: Optional[date] = None
    print_run: Optional[str] = None
    variant: Optional[str] = None
    direct: Optional[bool] = None
    writer: Optional[str] = None
    artist: Optional[str] = None
    penciller: Optional[str] = None
    inker: Optional[str] = None
    cover_artist: Optional[str] = None
    upc: Optional[str] = None
    img: Optional[str] = None


class ComicOut(ComicBase):
    id: int
    created_at: datetime

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
    point_of_purchase: Optional[str] = None
    buy_date: Optional[datetime] = None
    signed: Optional[bool] = False
    remarked: Optional[bool] = False
    condition: Optional[str] = None
    notes: Optional[str] = None


class UserComicCreate(UserComicBase):
    comic_id: int


class UserComicUpdate(BaseModel):
    count: Optional[int] = None
    paid_price: Optional[float] = None
    point_of_purchase: Optional[str] = None
    buy_date: Optional[datetime] = None
    signed: Optional[bool] = None
    remarked: Optional[bool] = None
    condition: Optional[str] = None
    notes: Optional[str] = None


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


# --- Scan (barcode lookup) ---

class ScanAddRequest(BaseModel):
    comic: ComicCreate
    user_comic: UserComicBase


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
    artist: Optional[str] = None
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


class KioskSignupOut(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None

    class Config:
        from_attributes = True


class KioskCardOut(BaseModel):
    """Customer-facing view of a pooled available comic - excludes cost/margin
    fields (paid_price, point_of_purchase, notes) that aren't the public's business."""
    id: int
    series: str
    volume: Optional[str] = None
    issue_number: Optional[str] = None
    cover_date: Optional[date] = None
    publisher: Optional[str] = None
    variant: Optional[str] = None
    img: Optional[str] = None
    cover_artist: Optional[str] = None
    artist: Optional[str] = None
    penciller: Optional[str] = None
    inker: Optional[str] = None
    writer: Optional[str] = None
    direct: Optional[bool] = None
    print_run: Optional[str] = None
    average_price: Optional[float] = None
    signed: bool = False
    remarked: bool = False
    condition: Optional[str] = None
    available: int = 0


class SeriesSearchResult(BaseModel):
    name: str
    count: int
