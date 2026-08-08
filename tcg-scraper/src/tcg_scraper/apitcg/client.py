from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from tcg_scraper.apitcg.exceptions import (
    ApiTcgAuthError,
    ApiTcgError,
    ApiTcgNotFoundError,
    ApiTcgQuotaExceededError,
    ApiTcgRateLimitError,
)
from tcg_scraper.apitcg.ratelimit import RateLimiter

logger = logging.getLogger(__name__)

# apitcg's real max page size (confirmed against a live response) - not a
# guess like the rest of the unverified shape notes elsewhere in this module.
MAX_PAGE_SIZE = 100


class ApiTcgClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.apitcg.com/api",
        auth_header: str = "x-api-key",
        max_calls_per_minute: int = 60,
        monthly_call_limit: int = 950,
    ):
        self._client = httpx.Client(
            base_url=base_url,
            headers={auth_header: api_key, "Accept": "application/json"},
            timeout=15.0,
        )
        self._rate_limiter = RateLimiter(max_calls_per_minute, 60.0)
        self._monthly_call_limit = monthly_call_limit
        # In-process only - resets on container restart. A real persistent
        # quota tracker would need a DB, which this stateless service
        # deliberately doesn't have (see tcg-scraper/README.md). This still
        # catches the main risk case (a runaway loop within one run).
        self._call_count = 0
        self._count_month: tuple[int, int] | None = None

    def calls_made_this_process(self) -> int:
        return self._call_count

    @property
    def monthly_call_limit(self) -> int:
        return self._monthly_call_limit

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ApiTcgClient:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def list_games(self) -> list[dict]:
        data = self._request("GET", "tcgs")
        return data if isinstance(data, list) else data.get("data", [])

    def get_game(self, slug: str) -> dict:
        return self._request("GET", f"tcgs/{slug}")

    def list_sets(self, tcg: str) -> list[dict]:
        data = self._request("GET", f"{tcg}/sets")
        return data if isinstance(data, list) else data.get("data", [])

    def get_set(self, tcg: str, set_id: str) -> dict:
        return self._request("GET", f"{tcg}/sets/{set_id}")

    def search_products(
        self, tcg: str, product_type: str = "card", set_id: str | None = None,
        page: int = 1, limit: int = MAX_PAGE_SIZE,
    ) -> dict:
        """Returns the raw paginated envelope: {"success", "data": [...],
        "total": N} - confirmed against a real response (see
        feature-requests/apitcg-calls). set_id filtering itself is still
        unverified (no discovery call confirmed the query param name for it)."""
        params: dict = {"tcg": tcg, "type": product_type, "page": page, "limit": min(limit, MAX_PAGE_SIZE)}
        if set_id is not None:
            params["set"] = set_id
        return self._request("GET", "products", params=params)

    def get_product(self, product_id: str) -> dict:
        return self._request("GET", f"products/{product_id}")

    def get_price_history(self, product_id: str) -> list[dict]:
        data = self._request("GET", f"history-prices/{product_id}")
        return data if isinstance(data, list) else data.get("data", [])

    def _check_monthly_quota(self) -> None:
        now = datetime.now(timezone.utc)
        month_key = (now.year, now.month)
        if month_key != self._count_month:
            self._count_month = month_key
            self._call_count = 0
        if self._call_count >= self._monthly_call_limit:
            raise ApiTcgQuotaExceededError(
                f"In-process apitcg.com call count ({self._call_count}) has reached the "
                f"configured limit ({self._monthly_call_limit}) for this month - refusing "
                "further calls. This counter resets on container restart and does not track "
                "calls made outside this process; check your real usage at apitcg.com before "
                "raising APITCG_MONTHLY_CALL_LIMIT."
            )
        self._call_count += 1

    def _request(self, method: str, path: str, **kwargs) -> dict:
        self._check_monthly_quota()
        self._rate_limiter.acquire()
        logger.info("-> %s %s/%s params=%s", method, self._client.base_url, path, kwargs.get("params"))
        response = self._client.request(method, path, **kwargs)
        logger.info("<- %s %s/%s status=%s", method, self._client.base_url, path, response.status_code)
        logger.debug("response body: %s", response.text)
        if response.status_code in (401, 403):
            raise ApiTcgAuthError(
                f"apitcg.com rejected the API key (status {response.status_code}) - "
                "verify APITCG_AUTH_HEADER matches their real Authentication docs"
            )
        if response.status_code == 404:
            raise ApiTcgNotFoundError(f"No apitcg.com resource at {path}")
        if response.status_code == 429:
            raise ApiTcgRateLimitError(f"apitcg.com rate limit hit: {response.text}")
        if response.is_error:
            raise ApiTcgError(f"apitcg.com API error {response.status_code}: {response.text}")
        return response.json()
