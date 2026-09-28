"""Embedding provider selection by config (mirrors the LLM factory)."""

from functools import lru_cache

from app.core.config import get_settings
from app.integrations.embeddings.base import EmbeddingProvider
from app.integrations.embeddings.mock import MockEmbeddingProvider


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    provider = get_settings().embedding_provider.lower()
    if provider == "mock":
        return MockEmbeddingProvider()
    raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {provider!r}")
