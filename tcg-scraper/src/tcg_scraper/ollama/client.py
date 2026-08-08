from __future__ import annotations

import base64
import io
import json
import logging

import httpx
from PIL import Image

from tcg_scraper.ollama.exceptions import (
    OllamaModelNotFoundError,
    OllamaResponseParseError,
    OllamaTimeoutError,
    OllamaUnreachableError,
)
from tcg_scraper.ollama.prompts import IDENTIFY_PROMPT

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(
        self,
        base_url: str = "http://ollama:11434",
        model: str = "moondream",
        timeout_seconds: float = 90.0,
        max_image_dimension: int = 1024,
    ):
        self._client = httpx.Client(base_url=base_url, timeout=timeout_seconds)
        self._model = model
        self._max_image_dimension = max_image_dimension

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> OllamaClient:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _downscale_to_base64(self, image_bytes: bytes) -> str:
        """Resize only - no cropping. The model should see the whole photo;
        this just bounds request size/latency, especially important on
        CPU-only inference."""
        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGB")
        longest_edge = max(img.size)
        if longest_edge > self._max_image_dimension:
            scale = self._max_image_dimension / longest_edge
            img = img.resize((int(img.width * scale), int(img.height * scale)))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("ascii")

    def identify_card(self, image_bytes: bytes) -> dict:
        """Returns the parsed structured extraction (name/number/set/etc.)
        plus the full raw Ollama response envelope under "_raw" so nothing
        is discarded, per the design rule of never losing scan history."""
        image_b64 = self._downscale_to_base64(image_bytes)

        try:
            logger.info("-> ollama /api/generate model=%s", self._model)
            response = self._client.post(
                "/api/generate",
                json={
                    "model": self._model,
                    "prompt": IDENTIFY_PROMPT,
                    "images": [image_b64],
                    "format": "json",
                    "stream": False,
                },
            )
        except httpx.ConnectError as exc:
            raise OllamaUnreachableError(f"Could not reach Ollama at {self._client.base_url}") from exc
        except httpx.TimeoutException as exc:
            raise OllamaTimeoutError(
                "Ollama inference timed out - CPU-only inference can be slow, try again shortly"
            ) from exc

        logger.info("<- ollama /api/generate status=%s", response.status_code)

        if response.status_code == 404:
            raise OllamaModelNotFoundError(
                f"Model '{self._model}' isn't pulled - run "
                f"`docker compose exec ollama ollama pull {self._model}`"
            )
        response.raise_for_status()

        envelope = response.json()
        raw_text = envelope.get("response", "")
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise OllamaResponseParseError(
                f"Model did not return valid JSON despite format='json': {raw_text!r}"
            ) from exc

        parsed["_raw"] = envelope
        return parsed
