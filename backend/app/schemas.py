from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr


# --- Auth ---

class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    is_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Comics ---

class ComicBase(BaseModel):
    publisher: Optional[str] = None
    name: str
    volume: Optional[str] = None
    number: Optional[str] = None
    print: Optional[str] = None
    cover: Optional[str] = None
    variant: Optional[str] = None
    direct: Optional[bool] = None
    writer: Optional[str] = None
    artist: Optional[str] = None
    pencils: Optional[str] = None
    inker: Optional[str] = None
    cover_artist: Optional[str] = None
    average_price: Optional[float] = None
    print_ratio: Optional[str] = None
    upc: Optional[str] = None


class ComicCreate(ComicBase):
    pass


class ComicUpdate(BaseModel):
    average_price: Optional[float] = None
    publisher: Optional[str] = None
    name: Optional[str] = None
    volume: Optional[str] = None
    number: Optional[str] = None
    print: Optional[str] = None
    cover: Optional[str] = None
    variant: Optional[str] = None
    direct: Optional[bool] = None
    writer: Optional[str] = None
    artist: Optional[str] = None
    pencils: Optional[str] = None
    inker: Optional[str] = None
    cover_artist: Optional[str] = None
    print_ratio: Optional[str] = None
    upc: Optional[str] = None


class ComicOut(ComicBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# --- UserComics ---

class UserComicBase(BaseModel):
    number_of_books: Optional[int] = 1
    price_paid: Optional[float] = None
    point_of_purchase: Optional[str] = None
    buy_date: Optional[datetime] = None
    signed: Optional[bool] = False
    remarked: Optional[bool] = False
    notes: Optional[str] = None
    sell_date: Optional[datetime] = None


class UserComicCreate(UserComicBase):
    comic_id: int


class UserComicUpdate(BaseModel):
    number_of_books: Optional[int] = None
    price_paid: Optional[float] = None
    point_of_purchase: Optional[str] = None
    buy_date: Optional[datetime] = None
    signed: Optional[bool] = None
    remarked: Optional[bool] = None
    notes: Optional[str] = None
    sell_date: Optional[datetime] = None


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

    class Config:
        from_attributes = True


# --- CSV Import ---

class CSVImportResult(BaseModel):
    success: bool
    filename: str
    total_rows: int
    imported: int
    failed: int
    new_comics_added_to_db: int
    existing_comics_linked: int
    errors: list[dict[str, Any]]


# --- Admin ---

class AdminUserOut(UserOut):
    csv_imports: list[Any] = []

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    is_admin: Optional[bool] = None


# --- Search ---

class ComicSearchParams(BaseModel):
    name: Optional[str] = None
    publisher: Optional[str] = None
    writer: Optional[str] = None
    artist: Optional[str] = None
    volume: Optional[str] = None
    number: Optional[str] = None
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
    user_email: str
    comic_name: Optional[str] = None

    class Config:
        from_attributes = True
