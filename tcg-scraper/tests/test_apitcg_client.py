import httpx
import pytest
import respx

from tcg_scraper.apitcg.client import ApiTcgClient
from tcg_scraper.apitcg.exceptions import ApiTcgAuthError, ApiTcgError, ApiTcgNotFoundError, ApiTcgRateLimitError


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
