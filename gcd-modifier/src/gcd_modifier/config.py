from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    gcd_username: str
    gcd_password: str
    gcd_base_url: str = "https://www.comics.org"

    postgres_user: str = "comicvault"
    postgres_password: str = "comicvault"
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "gcd"

    dump_dir: Path = Path("/data/dumps")

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
