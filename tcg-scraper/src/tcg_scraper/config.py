from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    apitcg_api_key: str
    # Confirmed against a real request (see feature-requests/apitcg-calls) -
    # note the api. subdomain, easy to miss.
    apitcg_base_url: str = "https://api.apitcg.com/api"
    apitcg_auth_header: str = "x-api-key"
    apitcg_max_calls_per_minute: int = 30
    # apitcg's real constraint is a MONTHLY quota (1,000 calls/month on the
    # free tier), not a per-minute burst - apitcg_max_calls_per_minute above
    # doesn't address this at all. This is a soft, in-process safety net
    # (resets on container restart, see ApiTcgClient) against an accidental
    # runaway loop within one run, not a true persistent quota tracker.
    apitcg_monthly_call_limit: int = 950

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
