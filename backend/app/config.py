from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080
    cors_origins: str = "http://localhost:3002"

    class Config:
        env_file = ".env"


settings = Settings()
