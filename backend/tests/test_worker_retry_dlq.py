"""Retry + DLQ tests for the AI worker (Phase 3 Slice 4)."""

import json

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.integrations.events.base import TOPIC_MEETING_ANALYSIS_DLQ
from app.integrations.events.memory import InMemoryEventBus
from app.integrations.llm.base import ClientContext
from app.integrations.llm.mock import MockLLMProvider
from app.models.intelligence import MeetingTopic
from app.models.meeting_status import MeetingStatus
from app.models.meetings import Meeting
from app.schemas.analysis import MeetingAnalysis
from app.workers.ai_worker import handle_meeting_created
from app.workers.outbox_publisher import publish_pending
from tests.conftest import auth_header, login, seed_tenant_user

DEMO = "selling the business, tax, son, succession"


class FlakyProvider:
    """Fails `fail_times` then succeeds (transient failure)."""

    model = "flaky"
    model_version = "0"
    prompt_version = "v1"

    def __init__(self, fail_times: int) -> None:
        self.remaining = fail_times
        self._delegate = MockLLMProvider()

    async def analyze_meeting(self, transcript: str, context: ClientContext) -> MeetingAnalysis:
        if self.remaining > 0:
            self.remaining -= 1
            raise RuntimeError("LLM temporarily unavailable")
        return await self._delegate.analyze_meeting(transcript, context)


class AlwaysFailProvider:
    model = "broken"
    model_version = "0"
    prompt_version = "v1"

    async def analyze_meeting(self, transcript: str, context: ClientContext) -> MeetingAnalysis:
        raise RuntimeError("LLM down")


async def _seed_and_publish(client, session, engine):
    await seed_tenant_user(session, slug="acme", email="a@acme.com")
    token = await login(client, "acme", "a@acme.com")
    cresp = await client.post("/api/v1/clients", json={"name": "John"}, headers=auth_header(token))
    cid = cresp.json()["id"]
    mresp = await client.post(
        "/api/v1/meetings",
        json={"client_id": cid, "title": "R", "occurred_at": "2026-09-22T10:00:00Z",
              "transcript": DEMO},
        headers=auth_header(token),
    )
    meeting_id = mresp.json()["id"]
    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    bus = InMemoryEventBus()
    async with maker() as s:
        await publish_pending(s, bus)
    payload = json.loads(bus.published[0][2].decode())
    return meeting_id, payload, maker


async def test_worker_retries_transient_failure_then_succeeds(
    client: AsyncClient, session: AsyncSession, engine
) -> None:
    meeting_id, payload, maker = await _seed_and_publish(client, session, engine)
    provider = FlakyProvider(fail_times=2)  # fails twice, succeeds on 3rd (max attempts=3)
    dlq = InMemoryEventBus()

    async with maker() as s:
        did = await handle_meeting_created(
            s, provider, event_id=payload["event_id"], payload=payload, dlq=dlq
        )
    assert did is True
    async with maker() as s:
        m = (await s.execute(select(Meeting).where(Meeting.id == meeting_id))).scalar_one()
        assert m.status == MeetingStatus.COMPLETED
    assert dlq.published == []  # never dead-lettered


async def test_worker_dead_letters_after_exhausting_retries(
    client: AsyncClient, session: AsyncSession, engine
) -> None:
    meeting_id, payload, maker = await _seed_and_publish(client, session, engine)
    provider = AlwaysFailProvider()
    dlq = InMemoryEventBus()

    async with maker() as s:
        did = await handle_meeting_created(
            s, provider, event_id=payload["event_id"], payload=payload, dlq=dlq
        )
    assert did is False

    async with maker() as s:
        m = (await s.execute(select(Meeting).where(Meeting.id == meeting_id))).scalar_one()
        assert m.status == MeetingStatus.FAILED
        # No intelligence persisted for a failed analysis.
        n_topics = (
            await s.execute(
                select(func.count()).select_from(MeetingTopic).where(
                    MeetingTopic.meeting_id == meeting_id
                )
            )
        ).scalar_one()
    assert n_topics == 0

    # Event was dead-lettered.
    assert len(dlq.published) == 1
    assert dlq.published[0][0] == TOPIC_MEETING_ANALYSIS_DLQ

    # A redelivery of the same event is NOT reprocessed (terminal marker recorded).
    async with maker() as s:
        again = await handle_meeting_created(
            s, provider, event_id=payload["event_id"], payload=payload, dlq=dlq
        )
    assert again is False
    assert len(dlq.published) == 1  # not dead-lettered a second time
