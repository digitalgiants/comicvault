from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    postgres_user: str = "comicvault"
    postgres_password: str = "comicvault"
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "coverbrowser"

    # Read-only - same gcd-modifier database the main backend already queries
    # (see vault/backend/app/gcd_database.py). Empty by default so `match`
    # simply refuses to run rather than silently matching against nothing.
    gcd_database_url: str = ""

    # coverbrowser.com has no published API or rate-limit policy, and started
    # returning 429s after a handful of manual requests during design - a
    # real, honest User-Agent and a conservative fixed delay between every
    # request are load-bearing, not cosmetic.
    user_agent: str = "ComicVault-CoverbrowserFetcher/0.1 (personal self-hosted comic catalog)"
    request_delay_seconds: float = 2.5

    @property
    def database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
