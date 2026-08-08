from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ApiTcgGame(BaseModel):
    """Mirrors an item from GET /api/tcgs. Exact field names beyond
    id/name are unverified against the real API - extra="allow" so an
    unexpected shape doesn't hard-fail parsing, just drops unknown fields
    from the typed view (raw dict is still available via model_extra)."""
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    logo: str | None = None


class ApiTcgSet(BaseModel):
    """Mirrors an item from GET /api/{tcg}/sets. Unverified beyond
    id/name/series - see ApiTcgGame's note."""
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    series: str | None = None
    code: str | None = None
    releaseDate: str | None = None
    printedTotal: int | None = None
    total: int | None = None


class ApiTcgImages(BaseModel):
    model_config = ConfigDict(extra="allow")

    small: str | None = None
    medium: str | None = None
    large: str | None = None


class ApiTcgProduct(BaseModel):
    """Mirrors a `type: "card"` item from GET /api/products - this shape
    IS confirmed, from apitcg.com's own openapi.json. The id field is
    `_id` (numeric) on the wire, per that spec."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: int = Field(alias="_id")
    type: str = "card"
    name: str
    description: str | None = None
    tcg: str
    serie: str | None = None
    set: str | None = None
    images: ApiTcgImages | None = None
    release_date: str | None = None
    code: str | None = None
    cardNumber: str | None = None
    attributes: dict | None = None
    markets: dict | None = None
    createdAt: str | None = None
    updatedAt: str | None = None
