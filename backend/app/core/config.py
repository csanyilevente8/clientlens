"""Application configuration via Pydantic settings.

Java/Spring analog: this is the equivalent of @ConfigurationProperties — values are
read from environment variables (and a local .env file), validated, and typed.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "ClientLens"
    version: str = "0.1.0"
    environment: str = "local"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance.

    lru_cache makes this a process-wide singleton (like a Spring @Bean), and lets
    tests override via dependency injection if needed.
    """
    return Settings()
