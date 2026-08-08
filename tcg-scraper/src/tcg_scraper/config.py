from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    apitcg_api_key: str
    # Base URL and auth header are unverified against the real API - confirmed
    # only via apitcg.com's published openapi.json, not a live request. Both
    # are env-driven so getting them right doesn't need a code change.
    apitcg_base_url: str = "https://apitcg.com/api"
    apitcg_auth_header: str = "x-api-key"
    apitcg_max_calls_per_minute: int = 30

    ollama_base_url: str = "http://ollama:11434"
    # Small/CPU-friendly by default - swap via env var once a GPU is available,
    # no code change needed. Verify current availability in Ollama's library
    # before relying on this exact name.
    ollama_vision_model: str = "moondream"
    ollama_timeout_seconds: float = 90.0
    ollama_max_image_dimension: int = 1024

    app_port: int = 9096


@lru_cache
def get_settings() -> Settings:
    return Settings()
