"""Vector store over Postgres/pgvector (ADR-004).

A focused async client for the transcript_chunks table (separate from the MySQL ORM). Access
patterns: insert chunks for a meeting, delete a meeting's chunks (idempotent re-index), and
tenant-scoped nearest-neighbour search.

Tenant scoping is enforced here too: search always filters by tenant_id, so semantic
retrieval can never cross tenants (ADR-008 applies to the vector store as well).
"""

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import get_settings


@dataclass
class ChunkHit:
    id: str
    meeting_id: str
    client_id: str
    content: str
    distance: float


def _vec_literal(vec: list[float]) -> str:
    # pgvector accepts a bracketed string like "[0.1,0.2,...]".
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"


_engine: AsyncEngine | None = None


def get_vector_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(get_settings().vector_database_url)
    return _engine


class VectorStore:
    def __init__(self, engine: AsyncEngine | None = None) -> None:
        self.engine = engine or get_vector_engine()

    async def delete_by_meeting(self, tenant_id: str, meeting_id: str) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(
                text(
                    "DELETE FROM transcript_chunks "
                    "WHERE tenant_id = :t AND meeting_id = :m"
                ),
                {"t": tenant_id, "m": meeting_id},
            )

    async def add_chunks(
        self,
        *,
        tenant_id: str,
        meeting_id: str,
        client_id: str,
        chunks: list[str],
        embeddings: list[list[float]],
    ) -> None:
        async with self.engine.begin() as conn:
            for i, (content, emb) in enumerate(zip(chunks, embeddings, strict=True)):
                await conn.execute(
                    text(
                        "INSERT INTO transcript_chunks "
                        "(id, tenant_id, meeting_id, client_id, chunk_index, content, embedding) "
                        "VALUES (:id, :t, :m, :c, :idx, :content, CAST(:emb AS vector))"
                    ),
                    {
                        "id": f"{meeting_id}:{i}",
                        "t": tenant_id,
                        "m": meeting_id,
                        "c": client_id,
                        "idx": i,
                        "content": content,
                        "emb": _vec_literal(emb),
                    },
                )

    async def search(
        self,
        *,
        tenant_id: str,
        query_embedding: list[float],
        top_k: int = 5,
        client_id: str | None = None,
    ) -> list[ChunkHit]:
        """Tenant-scoped nearest-neighbour search (cosine distance via <=>)."""
        filters = "tenant_id = :t"
        params: dict = {"t": tenant_id, "q": _vec_literal(query_embedding), "k": top_k}
        if client_id is not None:
            filters += " AND client_id = :c"
            params["c"] = client_id
        async with self.engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT id, meeting_id, client_id, content, "
                    "       embedding <=> CAST(:q AS vector) AS distance "
                    "FROM transcript_chunks "
                    f"WHERE {filters} "
                    "ORDER BY distance ASC "
                    "LIMIT :k"
                ),
                params,
            )
            return [
                ChunkHit(
                    id=row.id,
                    meeting_id=row.meeting_id,
                    client_id=row.client_id,
                    content=row.content,
                    distance=float(row.distance),
                )
                for row in result
            ]
