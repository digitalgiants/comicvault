from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    # Second, read-only connection to gcd-modifier's `gcd` database on the same
    # Postgres server - empty by default so GCD lookups are simply skipped
    # (falling through to Metron/ComicVine as before) if this isn't set.
    gcd_database_url: str = ""
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 5
    jwt_kiosk_expire_minutes: int = 480
    cors_origins: str = "http://localhost:3002"
    comic_scraper_url: str = "http://comic-scraper:9095"
    comicvine_api_key: str = ""
    tcg_scraper_url: str = "http://tcg-scraper:9096"
    # Empty by default so Google sign-in is simply unavailable (dormant, not
    # broken) until this is set - see app/google_auth.py. Only the client ID
    # is needed: verifying a Google Identity Services ID token is a public-key
    # signature check, not the server-side authorization-code exchange that
    # would need a client secret too.
    google_client_id: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
