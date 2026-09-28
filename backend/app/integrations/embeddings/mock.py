"""Deterministic mock embedder (default; dev + tests).

Hashes tokens into buckets of a fixed-dimension vector, then L2-normalizes. NOT semantically
meaningful, but DETERMINISTIC and stable — enough to exercise the full chunk->embed->store->
retrieve path without a real model or network. Same text always yields the same vector, and
texts sharing tokens yield partially-overlapping vectors (so retrieval is testable).
"""

import hashlib
import math
import re

from app.integrations.embeddings.base import EMBEDDING_DIM

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class MockEmbeddingProvider:
    dim = EMBEDDING_DIM

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = _TOKEN_RE.findall(text.lower())
        for tok in tokens:
            # Deterministic bucket + sign from a stable hash of the token.
            h = int(hashlib.sha256(tok.encode()).hexdigest(), 16)
            idx = h % self.dim
            sign = 1.0 if (h >> 8) & 1 else -1.0
            vec[idx] += sign
        # L2-normalize so cosine/L2 distances are well-behaved (zero vector -> leave as-is).
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec
