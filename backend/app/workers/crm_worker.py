"""CRM sync worker: 3rd consumer of IntelligenceExtracted -> push action items to the CRM.

Design (reasoned in the mentor session; SYSTEMDESING §11-13, failure scenario F):

  * Idempotent per (event_id, consumer_name="crm_worker") — independent of the AI and
    index workers consuming the same stream.
  * Per-action-item idempotency into the CRM via a STABLE Idempotency-Key derived from
    (event_id, action_item_id): a redelivery re-sends the same keys, so the CRM dedupes.
  * Error taxonomy drives control flow:
        CRMBadRequest (4xx)   -> PERMANENT. Dead-letter this event, keep consuming.
                                 Never trips the breaker.
        CRMUnavailable (5xx)  -> TRANSIENT. Propagates out of the pure core so the loop
                                 records a breaker failure and, once tripped, PAUSES
                                 consumption. Messages stay in Kafka -> eventual sync.

The pure core (handle_intelligence_extracted_for_crm) is Kafka-free and is what tests
exercise. The loop (run_crm_worker) owns Kafka + the breaker + pause/resume.
"""

from __future__ import annotations

import asyncio
import json

from aiokafka import AIOKafkaConsumer
from aiokafka.structs import TopicPartition
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.integrations.crm.base import (
    ActionItemSync,
    CRMBadRequest,
    CRMClient,
    CRMUnavailable,
)
from app.integrations.crm.factory import get_crm_client
from app.integrations.events.base import (
    TOPIC_CRM_SYNC_DLQ,
    TOPIC_INTELLIGENCE_EXTRACTED,
    EventBus,
)
from app.integrations.events.kafka import KafkaEventBus
from app.models.intelligence import ActionItem
from app.models.processed_event import ProcessedEvent
from app.workers.circuit_breaker import CircuitBreaker

CONSUMER_NAME = "crm_worker"


async def _already_processed(session: AsyncSession, event_id: str) -> bool:
    result = await session.execute(
        select(ProcessedEvent).where(
            ProcessedEvent.event_id == event_id,
            ProcessedEvent.consumer_name == CONSUMER_NAME,
        )
    )
    return result.scalar_one_or_none() is not None


async def _load_action_items(session: AsyncSession, meeting_id: str) -> list[ActionItem]:
    result = await session.execute(
        select(ActionItem).where(ActionItem.meeting_id == meeting_id)
    )
    return list(result.scalars().all())


async def handle_intelligence_extracted_for_crm(
    session: AsyncSession,
    crm: CRMClient,
    *,
    event_id: str,
    payload: dict,
    dlq: EventBus | None = None,
) -> bool:
    """Idempotently sync one meeting's action items to the CRM.

    Returns True if work was committed (marker written), False if skipped as a duplicate
    or dead-lettered as a permanent failure.

    Raises CRMUnavailable if the CRM is transiently down — deliberately NOT caught here:
    the caller (run_crm_worker) turns it into a breaker failure + pause so nothing is
    committed and the event is redelivered later. Nothing is persisted on this path.
    """
    if await _already_processed(session, event_id):
        return False

    meeting_id = payload["meeting_id"]
    items = await _load_action_items(session, meeting_id)

    try:
        for item in items:
            # Stable per-item key: a redelivery re-sends the same key so the CRM dedupes
            # (at-least-once delivery + idempotent sink = effectively once).
            idempotency_key = f"{event_id}:{item.id}"
            await crm.sync_action_item(
                idempotency_key,
                ActionItemSync(
                    client_ref=item.client_id,
                    description=item.description,
                    owner=item.owner,
                ),
            )
    except CRMBadRequest as exc:
        # Permanent: the CRM rejected the payload. Retrying can't help -> dead-letter the
        # whole event and record the marker so redelivery doesn't reprocess a known-bad one.
        session.add(ProcessedEvent(event_id=event_id, consumer_name=CONSUMER_NAME))
        await session.commit()
        if dlq is not None:
            await dlq.publish(
                TOPIC_CRM_SYNC_DLQ,
                key=meeting_id,
                value=json.dumps({**payload, "event_id": event_id, "error": str(exc)}).encode(),
            )
        return False
    # CRMUnavailable intentionally propagates (transient) — see docstring.

    # Success: record idempotency marker. No downstream event to emit (CRM is a sink).
    session.add(ProcessedEvent(event_id=event_id, consumer_name=CONSUMER_NAME))
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return False
    return True


async def run_crm_worker(
    session_maker: async_sessionmaker[AsyncSession],
    crm: CRMClient | None = None,
    dlq: EventBus | None = None,
    breaker: CircuitBreaker | None = None,
) -> None:
    """Consume IntelligenceExtracted and sync to the CRM, with a circuit breaker.

    When the breaker OPENS (enough consecutive transient CRM failures), we PAUSE the
    partitions and do NOT commit the offset — Kafka retains the backlog. After the
    cool-down the breaker half-opens; we resume and retry the same message. On success we
    commit and move on. This is what upholds "eventual sync" during a CRM outage.
    """
    settings = get_settings()
    crm = crm or get_crm_client()
    breaker = breaker or CircuitBreaker()
    owns_dlq = dlq is None
    if dlq is None:
        dlq = KafkaEventBus()
        await dlq.start()

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
            tp = TopicPartition(msg.topic, msg.partition)

            while True:
                # If the breaker is open, pause this partition and wait out the cool-down
                # WITHOUT committing — the message will be reprocessed after we resume.
                if not breaker.allows_request():
                    consumer.pause(tp)
                    await asyncio.sleep(breaker.seconds_until_retry())
                    continue
                consumer.resume(tp)
                try:
                    async with session_maker() as session:
                        await handle_intelligence_extracted_for_crm(
                            session, crm, event_id=event_id, payload=payload, dlq=dlq
                        )
                except CRMUnavailable:
                    # Transient: count toward the breaker and retry the SAME message
                    # (nothing was committed). Loop re-checks allows_request().
                    breaker.record_failure()
                    continue
                else:
                    breaker.record_success()
                    break

            await consumer.commit()
    finally:
        await consumer.stop()
        if owns_dlq:
            await dlq.stop()


if __name__ == "__main__":
    from app.core.db import SessionLocal

    asyncio.run(run_crm_worker(SessionLocal))
