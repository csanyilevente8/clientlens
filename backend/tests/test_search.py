"""Search / RAG endpoint tests (requires pgvector on localhost:5433)."""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import NullPool, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_retrieval_service
from app.integrations.embeddings.mock import MockEmbeddingProvider
from app.integrations.llm.mock import MockLLMProvider
from app.integrations.vectorstore.pgvector import VectorStore
from app.models.meetings import Meeting
from app.services.retrieval import RetrievalService
from app.workers.index_worker import handle_intelligence_extracted
from tests.conftest import auth_header, login, seed_tenant_user

TEST_VECTOR_URL = "postgresql+asyncpg://clientlens:clientlens@localhost:5433/clientlens_vectors"
TRANSCRIPT = "The client wants to sell the business and plan tax and succession to their son. " * 10


@pytest_asyncio.fixture(loop_scope="session")
async def vstore():
    engine = create_async_engine(TEST_VECTOR_URL, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            await conn.execute(select(1))
    except (OperationalError, OSError) as exc:  # pragma: no cover
        await engine.dispose()
        pytest.skip(f"pgvector not reachable ({exc})")
    yield VectorStore(engine)
    await engine.dispose()


async def test_search_returns_grounded_answer_and_sources(
    client, session, engine, vstore
) -> None:
    await seed_tenant_user(session, slug="acme", email="a@acme.com")
    token = await login(client, "acme", "a@acme.com")
    cid = (await client.post("/api/v1/clients", json={"name": "John"},
                             headers=auth_header(token))).json()["id"]
    await client.post(
        "/api/v1/meetings",
        json={"client_id": cid, "title": "R", "occurred_at": "2026-09-22T10:00:00Z",
              "transcript": TRANSCRIPT},
        headers=auth_header(token),
    )

    # Index the meeting (simulate the index worker running).
    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        m = (await s.execute(select(Meeting))).scalars().first()
    async with maker() as s:
        await handle_intelligence_extracted(
            s, MockEmbeddingProvider(), vstore,
            event_id=str(uuid.uuid4()),
            payload={"meeting_id": m.id, "tenant_id": m.tenant_id, "client_id": m.client_id},
        )

    # Override the endpoint's retrieval service to use the test vector store (port 5433).
    async def _override():
        async with maker() as s:
            yield RetrievalService(s, MockEmbeddingProvider(), vstore, MockLLMProvider())

    app = client._transport.app
    app.dependency_overrides[get_retrieval_service] = _override
    try:
        resp = await client.post(
            "/api/v1/search",
            json={"query": "selling the business and taxes", "client_id": cid},
            headers=auth_header(token),
        )
    finally:
        app.dependency_overrides.pop(get_retrieval_service, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"]
    assert len(body["sources"]) >= 1
    assert all(s["meeting_id"] == m.id for s in body["sources"])

    await vstore.delete_by_meeting(m.tenant_id, m.id)
