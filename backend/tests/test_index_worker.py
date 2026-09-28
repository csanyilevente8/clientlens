"""Indexing worker tests: chunk -> embed -> pgvector, idempotent (2nd consumer).

Requires the pgvector container running (docker compose up -d pgvector), reachable on
localhost:5433. Uses the real transcript_chunks table; cleans up per test.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import NullPool, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.integrations.embeddings.mock import MockEmbeddingProvider
from app.integrations.vectorstore.pgvector import VectorStore
from app.models.processed_event import ProcessedEvent
from app.workers.index_worker import CONSUMER_NAME, handle_intelligence_extracted
from tests.conftest import auth_header, login, seed_tenant_user

# Host-side URL for the pgvector container (compose maps 5433->5432).
TEST_VECTOR_URL = "postgresql+asyncpg://clientlens:clientlens@localhost:5433/clientlens_vectors"


@pytest_asyncio.fixture(loop_scope="session")
async def vector_store():
    engine = create_async_engine(TEST_VECTOR_URL, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            await conn.execute(select(1))
    except (OperationalError, OSError) as exc:  # pragma: no cover
        await engine.dispose()
        pytest.skip(f"pgvector not reachable on localhost:5433 ({exc})")
    store = VectorStore(engine)
    yield store
    await engine.dispose()


async def _create_meeting_and_get_intel_event(client, session, engine, transcript):
    await seed_tenant_user(session, slug="acme", email="a@acme.com")
    token = await login(client, "acme", "a@acme.com")
    cid = (await client.post("/api/v1/clients", json={"name": "John"},
                             headers=auth_header(token))).json()["id"]
    await client.post(
        "/api/v1/meetings",
        json={"client_id": cid, "title": "R", "occurred_at": "2026-09-22T10:00:00Z",
              "transcript": transcript},
        headers=auth_header(token),
    )
    # Build an IntelligenceExtracted-like payload directly (the AI worker would emit this).
    from app.models.meetings import Meeting
    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        m = (await s.execute(select(Meeting))).scalars().first()
    return maker, {
        "meeting_id": m.id, "tenant_id": m.tenant_id, "client_id": m.client_id,
    }, m


async def test_index_worker_chunks_and_stores(client, session, engine, vector_store):
    transcript = "The client wants to sell the business and plan tax and succession. " * 20
    maker, payload, m = await _create_meeting_and_get_intel_event(
        client, session, engine, transcript
    )
    event_id = str(uuid.uuid4())
    embedder = MockEmbeddingProvider()

    async with maker() as s:
        did = await handle_intelligence_extracted(
            s, embedder, vector_store, event_id=event_id, payload=payload
        )
    assert did is True

    # Chunks were stored and are retrievable via tenant-scoped search.
    q = (await embedder.embed(["sell the business tax"]))[0]
    hits = await vector_store.search(tenant_id=m.tenant_id, query_embedding=q, top_k=5)
    assert len(hits) >= 1
    assert all(h.meeting_id == m.id for h in hits)

    # cleanup
    await vector_store.delete_by_meeting(m.tenant_id, m.id)


async def test_index_worker_is_idempotent(client, session, engine, vector_store):
    transcript = "sell the business, tax planning, succession to son. " * 20
    maker, payload, m = await _create_meeting_and_get_intel_event(
        client, session, engine, transcript
    )
    event_id = str(uuid.uuid4())
    embedder = MockEmbeddingProvider()

    async with maker() as s:
        first = await handle_intelligence_extracted(
            s, embedder, vector_store, event_id=event_id, payload=payload
        )
    async with maker() as s:
        second = await handle_intelligence_extracted(
            s, embedder, vector_store, event_id=event_id, payload=payload
        )
    assert first is True
    assert second is False  # duplicate skipped

    # Exactly one marker for THIS consumer.
    async with maker() as s:
        markers = (
            await s.execute(
                select(ProcessedEvent).where(
                    ProcessedEvent.event_id == event_id,
                    ProcessedEvent.consumer_name == CONSUMER_NAME,
                )
            )
        ).scalars().all()
    assert len(markers) == 1

    await vector_store.delete_by_meeting(m.tenant_id, m.id)
