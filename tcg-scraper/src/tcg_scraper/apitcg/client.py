from __future__ import annotations

import logging

import httpx

from tcg_scraper.apitcg.exceptions import (
    ApiTcgAuthError,
    ApiTcgError,
    ApiTcgNotFoundError,
    ApiTcgRateLimitError,
)
from tcg_scraper.apitcg.ratelimit import RateLimiter

logger = logging.getLogger(__name__)


class ApiTcgClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://apitcg.com/api",
        auth_header: str = "x-api-key",
        max_calls_per_minute: int = 30,
    ):
        self._client = httpx.Client(
            base_url=base_url,
            headers={auth_header: api_key, "Accept": "application/json"},
            timeout=15.0,
        )
        self._rate_limiter = RateLimiter(max_calls_per_minute, 60.0)

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
        page: int = 1, limit: int = 250,
    ) -> dict:
        """Returns the raw paginated envelope (not just the item list) so
        callers can drive pagination off whatever total/page fields the
        real API actually returns - unverified shape, confirm at first use."""
        params: dict = {"tcg": tcg, "type": product_type, "page": page, "limit": limit}
        if set_id is not None:
            params["set"] = set_id
        return self._request("GET", "products", params=params)

    def get_product(self, product_id: str) -> dict:
        return self._request("GET", f"products/{product_id}")

    def get_price_history(self, product_id: str) -> list[dict]:
        data = self._request("GET", f"history-prices/{product_id}")
        return data if isinstance(data, list) else data.get("data", [])

    def _request(self, method: str, path: str, **kwargs) -> dict:
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
