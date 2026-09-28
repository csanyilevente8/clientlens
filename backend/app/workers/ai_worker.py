"""AI worker: consumes meeting.created events and runs analysis idempotently (§9, §13).

The consume loop (run_ai_worker) reads from Kafka; the pure core
(handle_meeting_created) does the idempotent processing and is what tests exercise.
"""

import asyncio
import json
import random

from aiokafka import AIOKafkaConsumer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.integrations.events.base import (
    TOPIC_MEETING_ANALYSIS_DLQ,
    TOPIC_MEETING_CREATED,
    EventBus,
)
from app.integrations.events.kafka import KafkaEventBus
from app.integrations.llm.base import LLMProvider
from app.integrations.llm.factory import get_llm_provider
from app.models.meeting_status import MeetingStatus
from app.models.meetings import Meeting
from app.models.processed_event import ProcessedEvent
from app.services.meeting_processing import analyze_meeting
from app.services.outbox import INTELLIGENCE_EXTRACTED, add_outbox_event

CONSUMER_NAME = "ai_worker"
MAX_ANALYSIS_ATTEMPTS = 3


async def _backoff(attempt: int) -> None:
    await asyncio.sleep(min(0.5 * (2 ** (attempt - 1)), 8.0) * random.random())


async def _already_processed(session: AsyncSession, event_id: str) -> bool:
    result = await session.execute(
        select(ProcessedEvent).where(
            ProcessedEvent.event_id == event_id,
            ProcessedEvent.consumer_name == CONSUMER_NAME,
        )
    )
    return result.scalar_one_or_none() is not None


async def handle_meeting_created(
    session: AsyncSession,
    provider: LLMProvider,
    *,
    event_id: str,
    payload: dict,
    dlq: EventBus | None = None,
) -> bool:
    """Idempotently process one MeetingCreated event. Returns True if work was committed,
    False if skipped (duplicate) or dead-lettered.

    Retries transient analysis failures (LLM threw) with backoff; after MAX attempts the
    meeting is marked FAILED, the event is published to the DLQ, and a terminal marker is
    recorded so redelivery does not reprocess a known-dead event. Validation failures are
    NON-retryable (analyze_meeting sets FAILED without raising).
    """
    if await _already_processed(session, event_id):
        return False

    meeting_id = payload["meeting_id"]

    async def _load_meeting() -> Meeting | None:
        return (
            await session.execute(select(Meeting).where(Meeting.id == meeting_id))
        ).scalar_one_or_none()

    meeting = await _load_meeting()
    if meeting is None:
        session.add(ProcessedEvent(event_id=event_id, consumer_name=CONSUMER_NAME))
        await session.commit()
        return False

    # Retry the analysis on transient failure. Each retry starts from a clean session
    # (rollback + re-fetch) so no partial state from a failed attempt persists.
    last_exc: Exception | None = None
    for attempt in range(1, MAX_ANALYSIS_ATTEMPTS + 1):
        try:
            await analyze_meeting(meeting, session, provider)
            last_exc = None
            break
        except Exception as exc:  # noqa: BLE001 — worker boundary: retry/DLQ decides fate
            last_exc = exc
            await session.rollback()
            meeting = await _load_meeting()  # re-fetch fresh for the next attempt
            if attempt < MAX_ANALYSIS_ATTEMPTS:
                await _backoff(attempt)

    if last_exc is not None:
        # All retries exhausted -> terminal failure. Persist FAILED + terminal marker, and
        # dead-letter the event for inspection/reprocessing.
        meeting.status = MeetingStatus.FAILED
        session.add(ProcessedEvent(event_id=event_id, consumer_name=CONSUMER_NAME))
        await session.commit()
        if dlq is not None:
            await dlq.publish(
                TOPIC_MEETING_ANALYSIS_DLQ,
                key=meeting.id,
                value=json.dumps({**payload, "event_id": event_id}).encode(),
            )
        return False

    # Success: record the idempotency marker AND emit IntelligenceExtracted (via the
    # outbox) in the SAME transaction as the work — so downstream consumers (indexing,
    # CRM sync) are guaranteed the intelligence is durable before they see the event.
    session.add(ProcessedEvent(event_id=event_id, consumer_name=CONSUMER_NAME))
    add_outbox_event(
        session,
        event_type=INTELLIGENCE_EXTRACTED,
        aggregate_id=meeting.id,
        tenant_id=meeting.tenant_id,
        payload={
            "meeting_id": meeting.id,
            "tenant_id": meeting.tenant_id,
            "client_id": meeting.client_id,
        },
    )
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return False
    return True


async def run_ai_worker(
    session_maker: async_sessionmaker[AsyncSession],
    provider: LLMProvider | None = None,
    dlq: EventBus | None = None,
) -> None:
    """Consume meeting.created from Kafka and process each event idempotently."""
    settings = get_settings()
    provider = provider or get_llm_provider()
    owns_dlq = dlq is None
    if dlq is None:
        dlq = KafkaEventBus()
        await dlq.start()
    consumer = AIOKafkaConsumer(
        TOPIC_MEETING_CREATED,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=CONSUMER_NAME,
        enable_auto_commit=False,  # commit offset only after we've processed
        auto_offset_reset="earliest",
    )
    await consumer.start()
    try:
        async for msg in consumer:
            payload = json.loads(msg.value.decode())
            event_id = payload.get("event_id") or (msg.key.decode() if msg.key else None)
            async with session_maker() as session:
                await handle_meeting_created(
                    session, provider, event_id=event_id, payload=payload, dlq=dlq
                )
            await consumer.commit()
    finally:
        await consumer.stop()
        if owns_dlq:
            await dlq.stop()


if __name__ == "__main__":
    from app.core.db import SessionLocal

    asyncio.run(run_ai_worker(SessionLocal))
