import httpx
import pytest
import respx

from tcg_scraper.apitcg.client import MAX_PAGE_SIZE, ApiTcgClient
from tcg_scraper.apitcg.exceptions import (
    ApiTcgAuthError, ApiTcgError, ApiTcgNotFoundError, ApiTcgQuotaExceededError, ApiTcgRateLimitError,
)


@pytest.fixture
def client():
    with ApiTcgClient("fake-key", base_url="https://apitcg.test/api", max_calls_per_minute=1000) as c:
        yield c


@respx.mock
def test_list_games(client):
    respx.get("https://apitcg.test/api/tcgs").mock(
        return_value=httpx.Response(200, json=[{"id": "pokemon", "name": "Pokemon"}])
    )
    games = client.list_games()
    assert games == [{"id": "pokemon", "name": "Pokemon"}]


@respx.mock
def test_401_raises_auth_error(client):
    respx.get("https://apitcg.test/api/tcgs").mock(return_value=httpx.Response(401))
    with pytest.raises(ApiTcgAuthError):
        client.list_games()


@respx.mock
def test_404_raises_not_found(client):
    respx.get("https://apitcg.test/api/products/missing").mock(return_value=httpx.Response(404))
    with pytest.raises(ApiTcgNotFoundError):
        client.get_product("missing")


@respx.mock
def test_429_raises_rate_limit(client):
    respx.get("https://apitcg.test/api/tcgs").mock(return_value=httpx.Response(429, text="slow down"))
    with pytest.raises(ApiTcgRateLimitError):
        client.list_games()


@respx.mock
def test_500_raises_generic_error(client):
    respx.get("https://apitcg.test/api/tcgs").mock(return_value=httpx.Response(500, text="boom"))
    with pytest.raises(ApiTcgError):
        client.list_games()


@respx.mock
def test_search_products_clamps_limit_to_max_page_size(client):
    route = respx.get("https://apitcg.test/api/products").mock(
        return_value=httpx.Response(200, json={"success": True, "data": [], "total": 0})
    )
    client.search_products("pokemon", limit=250)
    assert route.calls.last.request.url.params["limit"] == str(MAX_PAGE_SIZE)


@respx.mock
def test_monthly_quota_counter_blocks_once_limit_reached():
    respx.get("https://apitcg.test/api/tcgs").mock(return_value=httpx.Response(200, json=[]))
    with ApiTcgClient("fake-key", base_url="https://apitcg.test/api", max_calls_per_minute=1000, monthly_call_limit=2) as c:
        c.list_games()
        c.list_games()
        assert c.calls_made_this_process() == 2
        with pytest.raises(ApiTcgQuotaExceededError):
            c.list_games()


@respx.mock
def test_monthly_quota_counter_resets_on_month_rollover():
    respx.get("https://apitcg.test/api/tcgs").mock(return_value=httpx.Response(200, json=[]))
    with ApiTcgClient("fake-key", base_url="https://apitcg.test/api", max_calls_per_minute=1000, monthly_call_limit=1) as c:
        c.list_games()
        with pytest.raises(ApiTcgQuotaExceededError):
            c.list_games()
        # Simulate the calendar month rolling over - the counter should
        # reset rather than staying permanently tripped.
        c._count_month = (1999, 1)
        c.list_games()  # should succeed, not raise
        assert c.calls_made_this_process() == 1
