"""Indexing worker: consumes IntelligenceExtracted -> chunk -> embed -> store in pgvector.

The SECOND Kafka consumer of the same event stream. Its idempotency marker uses
consumer_name="index_worker", independent of the AI worker's marker for the same event —
which is exactly why processed_events keys on (event_id, consumer_name).

Cross-store idempotency (SYSTEMDESING §25): the marker is in MySQL but the chunks are in
pgvector — no shared transaction. We make the WORK itself idempotent (delete_by_meeting +
add_chunks) and do the pgvector writes BEFORE committing the MySQL marker. A crash between
them causes a redelivery that re-runs delete+add (same result) then commits the marker.
Effectively-once in effect, without a distributed transaction.
"""

import asyncio
import json

from aiokafka import AIOKafkaConsumer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.integrations.embeddings.base import EmbeddingProvider
from app.integrations.embeddings.factory import get_embedding_provider
from app.integrations.events.base import TOPIC_INTELLIGENCE_EXTRACTED
from app.integrations.vectorstore.pgvector import VectorStore
from app.models.meetings import Meeting
from app.models.processed_event import ProcessedEvent
from app.services.chunking import chunk_text

CONSUMER_NAME = "index_worker"


async def _already_processed(session: AsyncSession, event_id: str) -> bool:
    result = await session.execute(
        select(ProcessedEvent).where(
            ProcessedEvent.event_id == event_id,
            ProcessedEvent.consumer_name == CONSUMER_NAME,
        )
    )
    return result.scalar_one_or_none() is not None


async def handle_intelligence_extracted(
    session: AsyncSession,
    embedder: EmbeddingProvider,
    store: VectorStore,
    *,
    event_id: str,
    payload: dict,
) -> bool:
    """Idempotently index a meeting's transcript into the vector store."""
    if await _already_processed(session, event_id):
        return False

    meeting = (
        await session.execute(select(Meeting).where(Meeting.id == payload["meeting_id"]))
    ).scalar_one_or_none()
    if meeting is None:
        session.add(ProcessedEvent(event_id=event_id, consumer_name=CONSUMER_NAME))
        await session.commit()
        return False

    chunks = chunk_text(meeting.transcript)
    if chunks:
        embeddings = await embedder.embed(chunks)
        # Idempotent work: clear any existing chunks for this meeting, then insert. Safe to
        # re-run (redelivery) — same end state.
        await store.delete_by_meeting(meeting.tenant_id, meeting.id)
        await store.add_chunks(
            tenant_id=meeting.tenant_id,
            meeting_id=meeting.id,
            client_id=meeting.client_id,
            chunks=chunks,
            embeddings=embeddings,
        )

    # Commit the MySQL marker only AFTER the pgvector writes (cross-store ordering).
    session.add(ProcessedEvent(event_id=event_id, consumer_name=CONSUMER_NAME))
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return False
    return True


async def run_index_worker(
    session_maker: async_sessionmaker[AsyncSession],
    embedder: EmbeddingProvider | None = None,
    store: VectorStore | None = None,
) -> None:
    settings = get_settings()
    embedder = embedder or get_embedding_provider()
    store = store or VectorStore()
    consumer = AIOKafkaConsumer(
        TOPIC_INTELLIGENCE_EXTRACTED,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=CONSUMER_NAME,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
    )
    await consumer.start()
    try:
        async for msg in consumer:
            payload = json.loads(msg.value.decode())
            event_id = payload.get("event_id") or (msg.key.decode() if msg.key else None)
            async with session_maker() as session:
                await handle_intelligence_extracted(
                    session, embedder, store, event_id=event_id, payload=payload
                )
            await consumer.commit()
    finally:
        await consumer.stop()


if __name__ == "__main__":
    from app.core.db import SessionLocal

    asyncio.run(run_index_worker(SessionLocal))
