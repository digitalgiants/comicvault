from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    metron_username: str
    metron_password: str
    metron_base_url: str = "https://metron.cloud/api/"
    metron_max_calls_per_minute: int = 18

    postgres_user: str = "comic_scraper"
    postgres_password: str = "comic_scraper"
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "comic_scraper"

    app_port: int = 9095

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
