"""Retrieval + RAG service (SPEC §19, §20).

Combines semantic retrieval (pgvector) with structured data (MySQL) and an LLM to answer
natural-language questions about a client's history — grounded in retrieved evidence.

Tenant isolation: the caller passes the AUTHENTICATED tenant_id; every vector search and
SQL query is scoped to it, so retrieval can never cross tenants (ADR-008 applies here too).
The MCP layer (Phase 6) will call this same service rather than the DB directly (§19).
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.integrations.embeddings.base import EmbeddingProvider
from app.integrations.llm.base import LLMProvider
from app.integrations.vectorstore.pgvector import ChunkHit, VectorStore
from app.models.intelligence import ClientConcern, ClientGoal


@dataclass
class RetrievalResult:
    answer: str
    sources: list[ChunkHit]


class RetrievalService:
    def __init__(
        self,
        session: AsyncSession,
        embedder: EmbeddingProvider,
        store: VectorStore,
        llm: LLMProvider,
    ) -> None:
        self.session = session
        self.embedder = embedder
        self.store = store
        self.llm = llm

    async def _structured_context(self, tenant_id: str, client_id: str | None) -> str:
        """Pull a little structured context (goals/concerns) from MySQL, tenant-scoped."""
        if client_id is None:
            return ""
        goals = (
            await self.session.execute(
                select(ClientGoal).where(
                    ClientGoal.tenant_id == tenant_id, ClientGoal.client_id == client_id
                )
            )
        ).scalars().all()
        concerns = (
            await self.session.execute(
                select(ClientConcern).where(
                    ClientConcern.tenant_id == tenant_id,
                    ClientConcern.client_id == client_id,
                )
            )
        ).scalars().all()
        parts = []
        if goals:
            parts.append("Goals: " + "; ".join(g.description for g in goals))
        if concerns:
            parts.append("Concerns: " + "; ".join(c.description for c in concerns))
        return "\n".join(parts)

    async def answer(
        self, *, tenant_id: str, query: str, client_id: str | None = None
    ) -> RetrievalResult:
        settings = get_settings()
        query_vec = (await self.embedder.embed([query]))[0]

        # 1) semantic retrieval (tenant-scoped)
        hits = await self.store.search(
            tenant_id=tenant_id,
            query_embedding=query_vec,
            top_k=settings.retrieval_top_k,
            client_id=client_id,
        )

        # 2) assemble bounded context: retrieved chunks + structured data
        chunk_text = "\n".join(h.content for h in hits)
        structured = await self._structured_context(tenant_id, client_id)
        context = (structured + "\n" + chunk_text).strip()[: settings.retrieval_max_context_chars]

        # 3) RAG: LLM answers grounded in the context
        answer = await self.llm.answer_question(query, context)
        return RetrievalResult(answer=answer, sources=hits)
