"""CRM sync worker (pure-core) tests: idempotency, permanent -> DLQ, transient -> raises.

Exercises handle_intelligence_extracted_for_crm directly (Kafka-free). Uses fake CRM
clients to script success / permanent (4xx) / transient (5xx) outcomes. Requires MySQL
(loads ActionItem rows and writes processed_events), like the AI worker tests.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.integrations.crm.base import ActionItemSync, CRMBadRequest, CRMUnavailable, SyncResult
from app.integrations.events.base import TOPIC_CRM_SYNC_DLQ
from app.integrations.events.memory import InMemoryEventBus
from app.models.intelligence import ActionItem
from app.models.processed_event import ProcessedEvent
from app.workers.crm_worker import CONSUMER_NAME, handle_intelligence_extracted_for_crm
from tests.conftest import auth_header, login, seed_tenant_user


class RecordingCRM:
    """Succeeds and records every sync call."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, ActionItemSync]] = []

    async def sync_action_item(self, idempotency_key: str, item: ActionItemSync) -> SyncResult:
        self.calls.append((idempotency_key, item))
        return SyncResult(crm_id=f"crm_{len(self.calls)}", created=True)


class PermanentFailCRM:
    async def sync_action_item(self, idempotency_key: str, item: ActionItemSync) -> SyncResult:
        raise CRMBadRequest("400 bad payload")


class TransientFailCRM:
    async def sync_action_item(self, idempotency_key: str, item: ActionItemSync) -> SyncResult:
        raise CRMUnavailable("503 after retries")


async def _seed_meeting_with_action_items(client, session, engine, n_items=2):
    tenant, _ = await seed_tenant_user(session, slug="acme", email="a@acme.com")
    token = await login(client, "acme", "a@acme.com")
    cid = (
        await client.post("/api/v1/clients", json={"name": "John"}, headers=auth_header(token))
    ).json()["id"]
    mresp = await client.post(
        "/api/v1/meetings",
        json={"client_id": cid, "title": "R", "occurred_at": "2026-09-22T10:00:00Z",
              "transcript": "sell the business, tax, succession"},
        headers=auth_header(token),
    )
    meeting_id = mresp.json()["id"]

    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        for i in range(n_items):
            s.add(ActionItem(
                tenant_id=tenant.id, meeting_id=meeting_id, client_id=cid,
                description=f"Follow up #{i}", owner="advisor@acme.com",
            ))
        await s.commit()
    payload = {"meeting_id": meeting_id, "tenant_id": tenant.id, "client_id": cid}
    return maker, payload, meeting_id


async def test_syncs_all_action_items_and_marks_processed(
    client: AsyncClient, session: AsyncSession, engine
) -> None:
    maker, payload, _ = await _seed_meeting_with_action_items(client, session, engine, 3)
    crm = RecordingCRM()
    event_id = str(uuid.uuid4())

    async with maker() as s:
        did = await handle_intelligence_extracted_for_crm(
            s, crm, event_id=event_id, payload=payload, dlq=InMemoryEventBus()
        )
    assert did is True
    assert len(crm.calls) == 3
    # Keys are stable and derived from event_id + item id.
    assert all(k.startswith(event_id + ":") for k, _ in crm.calls)

    async with maker() as s:
        markers = (await s.execute(
            select(ProcessedEvent).where(
                ProcessedEvent.event_id == event_id,
                ProcessedEvent.consumer_name == CONSUMER_NAME,
            )
        )).scalars().all()
    assert len(markers) == 1


async def test_duplicate_event_is_skipped(
    client: AsyncClient, session: AsyncSession, engine
) -> None:
    maker, payload, _ = await _seed_meeting_with_action_items(client, session, engine, 1)
    event_id = str(uuid.uuid4())

    async with maker() as s:
        first = await handle_intelligence_extracted_for_crm(
            s, RecordingCRM(), event_id=event_id, payload=payload
        )
    crm2 = RecordingCRM()
    async with maker() as s:
        second = await handle_intelligence_extracted_for_crm(
            s, crm2, event_id=event_id, payload=payload
        )
    assert first is True
    assert second is False
    assert crm2.calls == []  # duplicate did not hit the CRM


async def test_permanent_failure_dead_letters_and_marks_processed(
    client: AsyncClient, session: AsyncSession, engine
) -> None:
    maker, payload, _ = await _seed_meeting_with_action_items(client, session, engine, 1)
    dlq = InMemoryEventBus()
    event_id = str(uuid.uuid4())

    async with maker() as s:
        did = await handle_intelligence_extracted_for_crm(
            s, PermanentFailCRM(), event_id=event_id, payload=payload, dlq=dlq
        )
    assert did is False
    assert len(dlq.published) == 1
    assert dlq.published[0][0] == TOPIC_CRM_SYNC_DLQ

    # Marker written so a redelivery won't reprocess a known-bad event.
    async with maker() as s:
        markers = (await s.execute(
            select(ProcessedEvent).where(ProcessedEvent.event_id == event_id)
        )).scalars().all()
    assert len(markers) == 1


async def test_transient_failure_propagates_and_persists_nothing(
    client: AsyncClient, session: AsyncSession, engine
) -> None:
    """A transient CRM outage must NOT commit a marker and must NOT dead-letter —
    it propagates so the loop can trip the breaker and retry later."""
    maker, payload, _ = await _seed_meeting_with_action_items(client, session, engine, 1)
    dlq = InMemoryEventBus()
    event_id = str(uuid.uuid4())

    with pytest.raises(CRMUnavailable):
        async with maker() as s:
            await handle_intelligence_extracted_for_crm(
                s, TransientFailCRM(), event_id=event_id, payload=payload, dlq=dlq
            )

    assert dlq.published == []  # not dead-lettered
    async with maker() as s:
        markers = (await s.execute(
            select(ProcessedEvent).where(ProcessedEvent.event_id == event_id)
        )).scalars().all()
    assert markers == []  # nothing committed -> event will be redelivered
