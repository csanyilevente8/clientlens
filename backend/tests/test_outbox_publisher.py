"""Outbox publisher tests (in-memory bus — no broker needed)."""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.integrations.events.base import TOPIC_MEETING_CREATED
from app.integrations.events.memory import InMemoryEventBus
from app.models.outbox import OutboxEvent
from app.workers.outbox_publisher import publish_pending
from tests.conftest import auth_header, login, seed_tenant_user


async def _make_meeting(client: AsyncClient, token: str) -> None:
    cresp = await client.post("/api/v1/clients", json={"name": "John"}, headers=auth_header(token))
    cid = cresp.json()["id"]
    await client.post(
        "/api/v1/meetings",
        json={
            "client_id": cid,
            "title": "Review",
            "occurred_at": "2026-09-22T10:00:00Z",
            "transcript": "selling the business, tax",
        },
        headers=auth_header(token),
    )


async def test_publisher_drains_outbox_and_marks_published(
    client: AsyncClient, session: AsyncSession, engine
) -> None:
    await seed_tenant_user(session, slug="acme", email="a@acme.com")
    token = await login(client, "acme", "a@acme.com")
    await _make_meeting(client, token)
    await _make_meeting(client, token)

    bus = InMemoryEventBus()
    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        count = await publish_pending(s, bus)

    # Both events published to the right topic...
    assert count == 2
    assert all(topic == TOPIC_MEETING_CREATED for topic, _, _ in bus.published)

    # ...and marked published in the DB (nothing left unpublished).
    async with maker() as s:
        remaining = (
            await s.execute(select(OutboxEvent).where(OutboxEvent.published_at.is_(None)))
        ).scalars().all()
    assert remaining == []


async def test_publisher_is_idempotent_across_runs(
    client: AsyncClient, session: AsyncSession, engine
) -> None:
    """A second run with nothing new publishes zero (already-published rows are skipped)."""
    await seed_tenant_user(session, slug="acme", email="a@acme.com")
    token = await login(client, "acme", "a@acme.com")
    await _make_meeting(client, token)

    bus = InMemoryEventBus()
    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        first = await publish_pending(s, bus)
    async with maker() as s:
        second = await publish_pending(s, bus)

    assert first == 1
    assert second == 0  # nothing left to publish
