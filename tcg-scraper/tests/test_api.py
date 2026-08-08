import pytest
from fastapi.testclient import TestClient

import tcg_scraper.api as api_module
from tcg_scraper.ollama.exceptions import OllamaModelNotFoundError


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("APITCG_API_KEY", "fake-key")
    api_module.get_settings.cache_clear()


def test_health():
    with TestClient(api_module.app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


def test_identify_maps_model_not_found_to_503():
    with TestClient(api_module.app) as client:
        def boom(image_bytes):
            raise OllamaModelNotFoundError("model not pulled")

        api_module.state["ollama"].identify_card = boom
        r = client.post("/identify", files={"file": ("card.jpg", b"fake-bytes", "image/jpeg")})
        assert r.status_code == 503
        assert "not pulled" in r.json()["detail"]
