"""AI worker tests: end-to-end async pipeline + idempotency (in-memory bus, mock LLM)."""

import json

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.integrations.events.memory import InMemoryEventBus
from app.integrations.llm.mock import MockLLMProvider
from app.models.intelligence import MeetingTopic
from app.models.meeting_status import MeetingStatus
from app.models.meetings import Meeting
from app.models.processed_event import ProcessedEvent
from app.workers.ai_worker import handle_meeting_created
from app.workers.outbox_publisher import publish_pending
from tests.conftest import auth_header, login, seed_tenant_user

DEMO = "Client is considering selling their business in 2-3 years; worried about taxes; son."


async def _seed_meeting(client: AsyncClient, token: str) -> str:
    cresp = await client.post("/api/v1/clients", json={"name": "John"}, headers=auth_header(token))
    cid = cresp.json()["id"]
    mresp = await client.post(
        "/api/v1/meetings",
        json={"client_id": cid, "title": "Review", "occurred_at": "2026-09-22T10:00:00Z",
              "transcript": DEMO},
        headers=auth_header(token),
    )
    return mresp.json()["id"]


async def test_worker_processes_event_end_to_end(
    client: AsyncClient, session: AsyncSession, engine
) -> None:
    await seed_tenant_user(session, slug="acme", email="a@acme.com")
    token = await login(client, "acme", "a@acme.com")
    meeting_id = await _seed_meeting(client, token)

    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    bus = InMemoryEventBus()
    provider = MockLLMProvider()

    # Publish outbox -> capture the event that would go to Kafka.
    async with maker() as s:
        await publish_pending(s, bus)
    _, _, value = bus.published[0]
    payload = json.loads(value.decode())
    event_id = payload["event_id"]

    # Worker handles the event.
    async with maker() as s:
        did_work = await handle_meeting_created(s, provider, event_id=event_id, payload=payload)
    assert did_work is True

    # Meeting COMPLETED and intelligence extracted.
    async with maker() as s:
        m = (await s.execute(select(Meeting).where(Meeting.id == meeting_id))).scalar_one()
        assert m.status == MeetingStatus.COMPLETED
        assert m.summary
        topics = (
            await s.execute(select(MeetingTopic).where(MeetingTopic.meeting_id == meeting_id))
        ).scalars().all()
        assert {t.topic for t in topics} >= {"business sale", "tax planning"}


async def test_worker_is_idempotent_on_duplicate_event(
    client: AsyncClient, session: AsyncSession, engine
) -> None:
    await seed_tenant_user(session, slug="acme", email="a@acme.com")
    token = await login(client, "acme", "a@acme.com")
    meeting_id = await _seed_meeting(client, token)

    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    bus = InMemoryEventBus()
    provider = MockLLMProvider()
    async with maker() as s:
        await publish_pending(s, bus)
    payload = json.loads(bus.published[0][2].decode())
    event_id = payload["event_id"]

    # Process the SAME event twice.
    async with maker() as s:
        first = await handle_meeting_created(s, provider, event_id=event_id, payload=payload)
    async with maker() as s:
        second = await handle_meeting_created(s, provider, event_id=event_id, payload=payload)

    assert first is True
    assert second is False  # duplicate skipped

    # Intelligence was written exactly once (no duplicates).
    async with maker() as s:
        topic_count = (
            await s.execute(
                select(func.count()).select_from(MeetingTopic).where(
                    MeetingTopic.meeting_id == meeting_id
                )
            )
        ).scalar_one()
        processed_count = (
            await s.execute(
                select(func.count()).select_from(ProcessedEvent).where(
                    ProcessedEvent.event_id == event_id
                )
            )
        ).scalar_one()
    assert topic_count >= 2
    assert processed_count == 1  # exactly one idempotency marker
