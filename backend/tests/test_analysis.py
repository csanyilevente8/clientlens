"""Tests for AI analysis: mock provider extraction + persistence with provenance."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.llm.base import ClientContext
from app.integrations.llm.mock import MockLLMProvider
from tests.conftest import auth_header, count_outbox_events, login, seed_tenant_user

DEMO_TRANSCRIPT = (
    "The client is considering selling their business within 2-3 years. "
    "They are worried about taxes and want to transfer the business to their son."
)


async def test_mock_provider_is_deterministic_and_keyword_based() -> None:
    provider = MockLLMProvider()
    a1 = await provider.analyze_meeting(DEMO_TRANSCRIPT, ClientContext(client_id="c1"))
    a2 = await provider.analyze_meeting(DEMO_TRANSCRIPT, ClientContext(client_id="c1"))
    assert a1 == a2  # deterministic
    assert "business sale" in a1.topics
    assert "tax planning" in a1.topics
    assert "tax implications" in a1.concerns
    assert any("succession" in g.description.lower() for g in a1.goals)


async def test_create_meeting_stages_outbox_event(
    client: AsyncClient, session: AsyncSession, engine
) -> None:
    """Slice 1: creating a meeting stages exactly one unpublished MeetingCreated outbox
    event, atomically with the meeting. (Full intelligence extraction is verified once the
    worker consumes the event — Slice 3.)"""
    await seed_tenant_user(session, slug="acme", email="a@acme.com")
    token = await login(client, "acme", "a@acme.com")
    cresp = await client.post("/api/v1/clients", json={"name": "John"}, headers=auth_header(token))
    client_id = cresp.json()["id"]

    mresp = await client.post(
        "/api/v1/meetings",
        json={
            "client_id": client_id,
            "title": "Annual Review",
            "occurred_at": "2026-09-22T10:00:00Z",
            "transcript": DEMO_TRANSCRIPT,
        },
        headers=auth_header(token),
    )
    assert mresp.status_code == 202
    meeting_id = mresp.json()["id"]

    events = await count_outbox_events(engine, meeting_id)
    assert len(events) == 1
    assert events[0].event_type == "MeetingCreated"
    assert events[0].published_at is None  # not yet published to Kafka
