from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class PublisherRef(BaseModel):
    id: int
    name: str


class SeriesRef(BaseModel):
    id: int
    name: str
    volume: int
    year_began: int


class Variant(BaseModel):
    name: str
    price: str | None = None
    sku: str = ""
    upc: str = ""
    image: str | None = None


class Credit(BaseModel):
    id: int
    creator: str
    role: list[dict]

    @property
    def role_names(self) -> list[str]:
        return [r["name"] for r in self.role]


class Issue(BaseModel):
    id: int
    series: SeriesRef
    publisher: PublisherRef | None = None
    number: str
    cover_date: date
    store_date: date | None = None
    upc: str = ""
    desc: str = ""
    image: str | None = None
    cover_hash: str | None = None
    variants: list[Variant] = []
    credits: list[Credit] = []
    cv_id: int | None = None
    gcd_id: int | None = None

    def _creators_with_role(self, role_substring: str) -> list[str]:
        needle = role_substring.lower()
        return [
            c.creator for c in self.credits if any(needle in r.lower() for r in c.role_names)
        ]

    @property
    def cover_artists(self) -> list[str]:
        return self._creators_with_role("cover")

    @property
    def writers(self) -> list[str]:
        return self._creators_with_role("writer")

    @property
    def pencillers(self) -> list[str]:
        return self._creators_with_role("pencil")

    @property
    def inkers(self) -> list[str]:
        return self._creators_with_role("ink")
