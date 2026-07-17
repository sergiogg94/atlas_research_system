from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(Path(__file__).parent.parent.parent / ".env"))

    # Database settings
    database_url: str = ""
    postgres_user: str = ""
    postgres_password: str = ""
    postgres_host: str = ""
    postgres_port: int = 5432
    postgres_db: str = ""

    # Redis settings
    redis_url: str = ""

    # API settings
    api_port: int = 8000
    debug: bool = True
    log_level: str = "DEBUG"

    # Timezone
    timezone: str = "America/Mexico_City"

    # LLM provider settings
    llm_provider: str = "echo"  # Default to "echo" for testing purposes
    ollama_base_url: str | None = None
    ollama_model: str = "qwen2.5:7b"


@lru_cache
def get_settings() -> Settings:
    return Settings()
