"""Regression tests for the "_id" bug: apitcg is Mongoose/MongoDB-backed
(confirmed via the embedded tcg/set sub-objects on a real captured product
response - see test_normalize_product.py's REAL_PRODUCT, which shows "_id",
"__v", "createdAt", "updatedAt" throughout). The standalone /tcgs and
/{tcg}/sets list endpoints were never captured directly, but reading "id"
instead of "_id" caused every game to collapse onto the same empty-string
slug and silently overwrite a single DB row on every sync - confirmed live
in production. These tests lock in the fix; they use inferred (Mongoose
convention), not captured, fixture shapes for the fields still marked
unverified in tcg-scraper/README.md."""
import pytest
from fastapi.testclient import TestClient

import tcg_scraper.api as api_module
import tcg_scraper.cache as cache_module


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("APITCG_API_KEY", "fake-key")
    api_module.get_settings.cache_clear()
    cache_module._store.clear()  # cached() is a module-level dict shared across tests


def test_list_games_uses_mongo_id_not_id():
    with TestClient(api_module.app) as client:
        api_module.state["apitcg"].list_games = lambda: [
            {"_id": "pokemon", "name": "Pokémon"},
            {"_id": "magic", "name": "Magic: The Gathering"},
            {"_id": "hololive", "name": "Hololive"},
        ]
        r = client.get("/games")
        assert r.status_code == 200
        games = r.json()
        slugs = {g["external_id"] for g in games}
        # The bug: all three would previously collapse to external_id="" since
        # none of them have an "id" key, only "_id".
        assert slugs == {"pokemon", "magic", "hololive"}
        assert len(games) == 3


def test_list_sets_uses_mongo_id_and_serie_and_snake_case_release_date():
    with TestClient(api_module.app) as client:
        api_module.state["apitcg"].list_sets = lambda tcg: [
            {
                "_id": "pokemon-xy-phantom-forces", "name": "XY - Phantom Forces",
                "code": "PHF", "serie": "xy", "release_date": "2014-11-05T00:00:00.000Z",
            },
        ]
        r = client.get("/games/pokemon/sets")
        assert r.status_code == 200
        [s] = r.json()
        assert s["external_id"] == "pokemon-xy-phantom-forces"
        assert s["set_code"] == "PHF"
        assert s["series_external_id"] == "xy"
        assert s["release_date"] == "2014-11-05T00:00:00.000Z"
