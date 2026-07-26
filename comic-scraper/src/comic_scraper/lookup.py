from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel

from comic_scraper.cache import LookupCache
from comic_scraper.metron.client import MetronClient
from comic_scraper.metron.exceptions import MetronNotFoundError
from comic_scraper.metron.models import Issue, Variant

logger = logging.getLogger(__name__)


class CreditInfo(BaseModel):
    creator: str
    roles: list[str]


class LookupResult(BaseModel):
    series_name: str
    issue_number: str
    cover_date: str
    variant_name: str | None
    cover_artists: list[str]
    matched_on: Literal["base_upc", "variant_upc"]
    source: Literal["cache", "metron"]
    # Optional with defaults so previously-cached rows (written before these fields
    # existed) still validate instead of 500ing on a cache hit.
    series_volume: int | None = None
    publisher_name: str | None = None
    store_date: str | None = None
    writers: list[str] = []
    pencillers: list[str] = []
    inkers: list[str] = []
    credits: list[CreditInfo] = []
    metron_id: int | None = None
    cv_id: int | None = None
    gcd_id: int | None = None
    image: str | None = None
    cover_hash: str | None = None


class UpcLookupService:
    def __init__(self, client: MetronClient, cache: LookupCache):
        self._client = client
        self._cache = cache

    def lookup(self, upc12: str, ean5: str | None = None) -> LookupResult | None:
        cached = self._cache.get(upc12, ean5)
        if cached is not None:
            logger.info("cache hit for upc12=%r ean5=%r", upc12, ean5)
            return LookupResult.model_validate(cached | {"source": "cache"})

        issue = self._find_issue(upc12, ean5)
        if issue is None:
            logger.info("no Metron issue found for upc12=%r ean5=%r", upc12, ean5)
            return None

        variant, matched_on = self._match_variant(issue, upc12, ean5)
        logger.info(
            "upc12=%r ean5=%r matched_on=%s variant_name=%r",
            upc12,
            ean5,
            matched_on,
            variant.name if variant else None,
        )

        result = LookupResult(
            series_name=issue.series.name,
            series_volume=issue.series.volume,
            publisher_name=issue.publisher.name if issue.publisher else None,
            issue_number=issue.number,
            cover_date=str(issue.cover_date),
            store_date=str(issue.store_date) if issue.store_date else None,
            variant_name=variant.name if variant else None,
            cover_artists=issue.cover_artists,
            writers=issue.writers,
            pencillers=issue.pencillers,
            inkers=issue.inkers,
            credits=[CreditInfo(creator=c.creator, roles=c.role_names) for c in issue.credits],
            matched_on=matched_on,
            source="metron",
            metron_id=issue.id,
            cv_id=issue.cv_id,
            gcd_id=issue.gcd_id,
            image=(variant.image if variant and variant.image else issue.image),
            cover_hash=issue.cover_hash,
        )
        self._cache.set(upc12, ean5, result.model_dump(exclude={"source"}))
        return result

    def _find_issue(self, upc12: str, ean5: str | None) -> Issue | None:
        # Metron stores UPC+EAN5 concatenated in Issue.upc; older comics with no
        # EAN-5 supplement, or inconsistently-entered records, only have the bare UPC.
        if ean5:
            full_code = f"{upc12}{ean5}"
            logger.info("querying Metron with concatenated code %r", full_code)
            issue = self._fetch(full_code)
            if issue is not None:
                return issue
            logger.info(
                "no match for concatenated code %r, falling back to bare upc12=%r",
                full_code,
                upc12,
            )
        else:
            logger.info("no ean5 provided, querying Metron with bare upc12=%r", upc12)

        return self._fetch(upc12)

    def _fetch(self, code: str) -> Issue | None:
        try:
            return self._client.get_issue_by_upc(code)
        except MetronNotFoundError:
            return None

    @staticmethod
    def _match_variant(
        issue: Issue, upc12: str, ean5: str | None
    ) -> tuple[Variant | None, Literal["base_upc", "variant_upc"]]:
        if not ean5:
            return None, "base_upc"

        full_code = f"{upc12}{ean5}"
        for variant in issue.variants:
            if variant.upc in (full_code, ean5):
                return variant, "variant_upc"
        return None, "base_upc"
