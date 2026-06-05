from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    postgres_user: str
    postgres_password: str
    postgres_host: str
    postgres_port: int
    postgres_db: str
    api_port: int = 8000
    debug: bool = True

    class Config:
        env_file = str(Path(__file__).parent.parent.parent / ".env")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
