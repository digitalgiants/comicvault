import io
import json

import httpx
import pytest
import respx
from PIL import Image

from tcg_scraper.ollama.client import OllamaClient
from tcg_scraper.ollama.exceptions import (
    OllamaModelNotFoundError,
    OllamaResponseParseError,
    OllamaTimeoutError,
    OllamaUnreachableError,
)

BASE_URL = "https://ollama.test"


@pytest.fixture
def client():
    with OllamaClient(base_url=BASE_URL, model="moondream", max_image_dimension=64) as c:
        yield c


@pytest.fixture
def fake_image_bytes():
    img = Image.new("RGB", (100, 100), color=(0, 128, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@respx.mock
def test_identify_success(client, fake_image_bytes):
    inner = {"name": "Pikachu", "number": "025/165", "set": "Surging Sparks", "language": "English",
              "variant": None, "game": "pokemon", "confidence": 0.97}
    respx.post(f"{BASE_URL}/api/generate").mock(
        return_value=httpx.Response(200, json={"response": json.dumps(inner), "done": True})
    )
    result = client.identify_card(fake_image_bytes)
    assert result["name"] == "Pikachu"
    assert result["number"] == "025/165"
    assert "_raw" in result


@respx.mock
def test_model_not_found(client, fake_image_bytes):
    respx.post(f"{BASE_URL}/api/generate").mock(return_value=httpx.Response(404))
    with pytest.raises(OllamaModelNotFoundError):
        client.identify_card(fake_image_bytes)


@respx.mock
def test_unreachable(client, fake_image_bytes):
    respx.post(f"{BASE_URL}/api/generate").mock(side_effect=httpx.ConnectError("no route"))
    with pytest.raises(OllamaUnreachableError):
        client.identify_card(fake_image_bytes)


@respx.mock
def test_timeout(client, fake_image_bytes):
    respx.post(f"{BASE_URL}/api/generate").mock(side_effect=httpx.TimeoutException("too slow"))
    with pytest.raises(OllamaTimeoutError):
        client.identify_card(fake_image_bytes)


@respx.mock
def test_bad_json_response(client, fake_image_bytes):
    respx.post(f"{BASE_URL}/api/generate").mock(
        return_value=httpx.Response(200, json={"response": "not valid json {{{", "done": True})
    )
    with pytest.raises(OllamaResponseParseError):
        client.identify_card(fake_image_bytes)
