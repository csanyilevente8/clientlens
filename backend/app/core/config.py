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

    # Database (MySQL). Defaults target the docker-compose service.
    # Java/Spring analog: spring.datasource.* properties.
    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "clientlens"
    db_password: str = "clientlens"
    db_name: str = "clientlens"

    # JWT auth (RS256). Keys loaded from PEM files for local dev; in production these
    # would be injected via secrets (SPEC §26/§34). See backend/keys/README.md.
    jwt_algorithm: str = "RS256"
    jwt_private_key_path: str = "keys/jwt_private_dev.pem"
    jwt_public_key_path: str = "keys/jwt_public_dev.pem"
    access_token_expire_minutes: int = 30

    # LLM provider selection (SPEC §46). "mock" is default for dev/tests.
    llm_provider: str = "mock"

    # Kafka / event bus.
    kafka_bootstrap_servers: str = "localhost:9092"

    # Embeddings + vector store (pgvector). Separate from MySQL (ADR-004).
    embedding_provider: str = "mock"
    vector_db_host: str = "localhost"
    vector_db_port: int = 5432
    vector_db_user: str = "clientlens"
    vector_db_password: str = "clientlens"
    vector_db_name: str = "clientlens_vectors"

    # Retrieval / RAG params (SPEC §20).
    retrieval_top_k: int = 5
    retrieval_max_context_chars: int = 4000

    @property
    def vector_database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.vector_db_user}:{self.vector_db_password}"
            f"@{self.vector_db_host}:{self.vector_db_port}/{self.vector_db_name}"
        )

    @property
    def jwt_private_key(self) -> str:
        with open(self.jwt_private_key_path) as f:
            return f.read()

    @property
    def jwt_public_key(self) -> str:
        with open(self.jwt_public_key_path) as f:
            return f.read()

    @property
    def database_url(self) -> str:
        """Async SQLAlchemy URL using the asyncmy driver."""
        return (
            f"mysql+asyncmy://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance.

    lru_cache makes this a process-wide singleton (like a Spring @Bean), and lets
    tests override via dependency injection if needed.
    """
    return Settings()
