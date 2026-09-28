"""Outbox polling publisher (SYSTEMDESING §10).

Reads unpublished outbox rows and publishes them to the event bus, then marks them
published. This is the "drain the outbox" half of the pattern.

At-least-once: if we publish to Kafka and then crash before marking published_at, the row
is picked up again on the next run and re-published. Therefore consumers MUST be idempotent
(Slice 3). We accept possible duplicates in exchange for never losing an event.

Maps outbox event_type -> Kafka topic.
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.integrations.events.base import TOPIC_MEETING_CREATED, EventBus
from app.models.outbox import OutboxEvent
from app.services.outbox import MEETING_CREATED
from app.utils.time import utcnow

_EVENT_TYPE_TO_TOPIC: dict[str, str] = {
    MEETING_CREATED: TOPIC_MEETING_CREATED,
}


async def publish_pending(session: AsyncSession, bus: EventBus, *, batch_size: int = 100) -> int:
    """Publish one batch of unpublished outbox events. Returns how many were published."""
    result = await session.execute(
        select(OutboxEvent)
        .where(OutboxEvent.published_at.is_(None))
        .order_by(OutboxEvent.created_at)
        .limit(batch_size)
    )
    events = list(result.scalars().all())

    for event in events:
        topic = _EVENT_TYPE_TO_TOPIC.get(event.event_type)
        if topic is None:
            # Unknown event type — skip marking so it can be handled once mapped.
            continue
        # Publish first; mark published after. If we crash between, the row stays
        # unpublished and gets re-published next run (at-least-once).
        await bus.publish(topic, key=event.aggregate_id, value=event.payload.encode())
        event.published_at = utcnow()

    await session.commit()
    return len(events)


async def run_publisher_loop(
    session_maker: async_sessionmaker[AsyncSession],
    bus: EventBus,
    *,
    poll_interval_seconds: float = 1.0,
) -> None:
    """Continuously drain the outbox. Runs as a background task / separate process."""
    await bus.start()
    try:
        while True:
            async with session_maker() as session:
                published = await publish_pending(session, bus)
            # Back off only when idle, to avoid a tight loop.
            if published == 0:
                await asyncio.sleep(poll_interval_seconds)
    finally:
        await bus.stop()
