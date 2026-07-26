import httpx
import pytest
import respx

from comic_scraper.metron.client import MetronClient
from comic_scraper.metron.exceptions import MetronAuthError, MetronRateLimitError


@respx.mock
def test_get_issue_by_upc_returns_none_on_empty_results() -> None:
    respx.get("https://metron.cloud/api/issue/").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    client = MetronClient("user", "pass")

    assert client.get_issue_by_upc("000000000000") is None


@respx.mock
def test_401_raises_auth_error() -> None:
    respx.get("https://metron.cloud/api/issue/").mock(return_value=httpx.Response(401))
    client = MetronClient("user", "pass")

    with pytest.raises(MetronAuthError):
        client.get_issue_by_upc("000000000000")


@respx.mock
def test_429_raises_rate_limit_error() -> None:
    respx.get("https://metron.cloud/api/issue/").mock(return_value=httpx.Response(429))
    client = MetronClient("user", "pass")

    with pytest.raises(MetronRateLimitError):
        client.get_issue_by_upc("000000000000")
