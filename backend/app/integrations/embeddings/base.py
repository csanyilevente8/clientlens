"""Embedding provider abstraction (SPEC §18; mirrors LLMProvider).

Turns text into fixed-dimension vectors for semantic search. Business/worker code depends
on this protocol; a deterministic mock is the default (free, stable tests). A real model
(sentence-transformers / OpenAI / Ollama) can be added behind the same interface later.
"""

from typing import Protocol

EMBEDDING_DIM = 384


class EmbeddingProvider(Protocol):
    dim: int

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text."""
        ...
