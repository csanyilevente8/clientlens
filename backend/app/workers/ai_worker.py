"""AI worker: consumes meeting.created events and runs analysis idempotently (§9, §13).

The consume loop (run_ai_worker) reads from Kafka; the pure core
(handle_meeting_created) does the idempotent processing and is what tests exercise.
"""

import asyncio
import json

from aiokafka import AIOKafkaConsumer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.integrations.events.base import TOPIC_MEETING_CREATED
from app.integrations.llm.base import LLMProvider
from app.integrations.llm.factory import get_llm_provider
from app.models.meetings import Meeting
from app.models.processed_event import ProcessedEvent
from app.services.meeting_processing import analyze_meeting

CONSUMER_NAME = "ai_worker"


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
) -> bool:
    """Idempotently process one MeetingCreated event. Returns True if work was done,
    False if it was a duplicate that was skipped.

    Work (analysis + intelligence rows + status) and the ProcessedEvent marker are committed
    in ONE transaction, so they are always consistent. The unique constraint on
    (event_id, consumer_name) is the safety net against concurrent duplicates.
    """
    # Cheap common-case check.
    if await _already_processed(session, event_id):
        return False

    meeting = (
        await session.execute(select(Meeting).where(Meeting.id == payload["meeting_id"]))
    ).scalar_one_or_none()
    if meeting is None:
        # Meeting vanished (deleted before processing) — mark processed so we don't loop.
        session.add(ProcessedEvent(event_id=event_id, consumer_name=CONSUMER_NAME))
        await session.commit()
        return False

    # Do the work (mutates meeting + stages intelligence rows on the session).
    await analyze_meeting(meeting, session, provider)

    # Record the idempotency marker in the SAME transaction as the work.
    session.add(ProcessedEvent(event_id=event_id, consumer_name=CONSUMER_NAME))
    try:
        await session.commit()
    except IntegrityError:
        # Concurrent duplicate beat us to the unique (event_id, consumer_name) — roll back
        # our duplicate work. The other transaction owns the result.
        await session.rollback()
        return False
    return True


async def run_ai_worker(
    session_maker: async_sessionmaker[AsyncSession],
    provider: LLMProvider | None = None,
) -> None:
    """Consume meeting.created from Kafka and process each event idempotently."""
    settings = get_settings()
    provider = provider or get_llm_provider()
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
            # event_id travels in the body (set by the publisher); fall back to the key.
            event_id = payload.get("event_id") or (msg.key.decode() if msg.key else None)
            async with session_maker() as session:
                await handle_meeting_created(
                    session, provider, event_id=event_id, payload=payload
                )
            await consumer.commit()
    finally:
        await consumer.stop()


if __name__ == "__main__":
    from app.core.db import SessionLocal

    asyncio.run(run_ai_worker(SessionLocal))
