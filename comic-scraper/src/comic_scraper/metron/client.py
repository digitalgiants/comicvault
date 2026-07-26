from __future__ import annotations

import logging

import httpx

from comic_scraper.metron.exceptions import (
    MetronAuthError,
    MetronError,
    MetronNotFoundError,
    MetronRateLimitError,
)
from comic_scraper.metron.models import Issue
from comic_scraper.metron.ratelimit import RateLimiter

logger = logging.getLogger(__name__)


class MetronClient:
    def __init__(
        self,
        username: str,
        password: str,
        base_url: str = "https://metron.cloud/api/",
        max_calls_per_minute: int = 18,
    ):
        self._client = httpx.Client(
            base_url=base_url,
            auth=(username, password),
            timeout=10.0,
            headers={"Accept": "application/json"},
        )
        # Kept under Metron's documented 20/min burst limit - a batch lookup can need
        # up to 2 calls per item (concatenated code, then bare-UPC fallback).
        self._rate_limiter = RateLimiter(max_calls_per_minute, 60.0)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> MetronClient:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def get_issue_by_upc(self, upc: str) -> Issue | None:
        results = self._request("GET", "issue/", params={"upc": upc})["results"]
        logger.info("upc=%r matched %d result(s) on the base issue filter", upc, len(results))
        if not results:
            return None
        return self.get_issue(results[0]["id"])

    def get_issue(self, issue_id: int) -> Issue:
        data = self._request("GET", f"issue/{issue_id}/")
        issue = Issue.model_validate(data)
        logger.info(
            "issue id=%s upc=%r has %d variant(s): %s",
            issue_id,
            issue.upc,
            len(issue.variants),
            [v.upc for v in issue.variants],
        )
        return issue

    def _request(self, method: str, path: str, **kwargs) -> dict:
        self._rate_limiter.acquire()
        logger.info("-> %s %s%s params=%s", method, self._client.base_url, path, kwargs.get("params"))
        response = self._client.request(method, path, **kwargs)
        logger.info("<- %s %s%s status=%s", method, self._client.base_url, path, response.status_code)
        logger.debug("response body: %s", response.text)
        if response.status_code == 401:
            raise MetronAuthError("Invalid or missing Metron credentials")
        if response.status_code == 404:
            raise MetronNotFoundError(f"No Metron resource at {path}")
        if response.status_code == 429:
            raise MetronRateLimitError(
                f"Metron rate limit hit (burst 20/min, sustained 5000/day): {response.text}"
            )
        if response.is_error:
            raise MetronError(f"Metron API error {response.status_code}: {response.text}")
        return response.json()
