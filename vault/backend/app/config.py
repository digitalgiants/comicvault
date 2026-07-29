from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 5
    jwt_kiosk_expire_minutes: int = 480
    cors_origins: str = "http://localhost:3002"
    comic_scraper_url: str = "http://comic-scraper:9095"
    comicvine_api_key: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
