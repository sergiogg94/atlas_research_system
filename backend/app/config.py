from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(Path(__file__).parent.parent.parent / ".env"))

    # Database settings
    database_url: str = Field(validation_alias=AliasChoices("DATABASE_URL", "database_url"))
    postgres_user: str = Field(validation_alias=AliasChoices("POSTGRES_USER", "postgres_user"))
    postgres_password: str = Field(
        validation_alias=AliasChoices("POSTGRES_PASSWORD", "postgres_password")
    )
    postgres_host: str = Field(validation_alias=AliasChoices("POSTGRES_HOST", "postgres_host"))
    postgres_port: int = Field(validation_alias=AliasChoices("POSTGRES_PORT", "postgres_port"))
    postgres_db: str = Field(validation_alias=AliasChoices("POSTGRES_DB", "postgres_db"))

    # Redis settings
    redis_url: str = Field(validation_alias=AliasChoices("REDIS_URL", "redis_url"))

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
