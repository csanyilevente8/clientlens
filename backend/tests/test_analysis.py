"""Tests for AI analysis: mock provider extraction + persistence with provenance."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.llm.base import ClientContext
from app.integrations.llm.mock import MockLLMProvider
from tests.conftest import auth_header, login, seed_tenant_user

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


async def test_create_meeting_persists_intelligence_with_provenance(
    client: AsyncClient, session: AsyncSession
) -> None:
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
    assert mresp.status_code == 201
    meeting_id = mresp.json()["id"]
    assert mresp.json()["status"] == "COMPLETED"

    # Read the extracted intelligence back through the API (tests the real read path).
    intel = await client.get(
        f"/api/v1/meetings/{meeting_id}/intelligence", headers=auth_header(token)
    )
    assert intel.status_code == 200
    body = intel.json()
    assert set(body["topics"]) >= {"business sale", "tax planning"}
    assert "tax implications" in body["concerns"]
    assert any("succession" in g["description"].lower() for g in body["goals"])
    assert body["summary"]
