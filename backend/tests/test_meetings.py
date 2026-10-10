"""Meeting CRUD + tenant-isolation tests."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_header, login, seed_tenant_user


async def _create_client(client: AsyncClient, token: str, name: str = "John Smith") -> str:
    resp = await client.post("/api/v1/clients", json={"name": name}, headers=auth_header(token))
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_create_meeting_accepts_and_stays_created(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Async ingestion (Slice 1): create returns 202 and the meeting sits at CREATED.

    Analysis is now asynchronous (worker), so it is NOT COMPLETED on return. An outbox
    event must have been recorded atomically with the meeting.
    """
    await seed_tenant_user(session, slug="acme", email="a@acme.com")
    token = await login(client, "acme", "a@acme.com")
    client_id = await _create_client(client, token)

    resp = await client.post(
        "/api/v1/meetings",
        json={
            "client_id": client_id,
            "title": "Annual Review",
            "occurred_at": "2026-09-22T10:00:00Z",
            "transcript": "Client is considering selling their business in 2-3 years.",
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "CREATED"
    assert body["client_id"] == client_id


async def test_create_meeting_rejects_other_tenants_client(
    client: AsyncClient, session: AsyncSession
) -> None:
    await seed_tenant_user(session, slug="acme", email="a@acme.com")
    await seed_tenant_user(session, slug="beta", email="b@beta.com")
    token_a = await login(client, "acme", "a@acme.com")
    token_b = await login(client, "beta", "b@beta.com")
    acme_client_id = await _create_client(client, token_a)

    # Beta tries to create a meeting for Acme's client -> 404 (client not found in Beta's tenant)
    resp = await client.post(
        "/api/v1/meetings",
        json={
            "client_id": acme_client_id,
            "title": "Sneaky",
            "occurred_at": "2026-09-22T10:00:00Z",
            "transcript": "x",
        },
        headers=auth_header(token_b),
    )
    assert resp.status_code == 404


async def test_meeting_isolation_on_read(client: AsyncClient, session: AsyncSession) -> None:
    await seed_tenant_user(session, slug="acme", email="a@acme.com")
    await seed_tenant_user(session, slug="beta", email="b@beta.com")
    token_a = await login(client, "acme", "a@acme.com")
    token_b = await login(client, "beta", "b@beta.com")
    client_id = await _create_client(client, token_a)

    created = await client.post(
        "/api/v1/meetings",
        json={
            "client_id": client_id,
            "title": "Annual Review",
            "occurred_at": "2026-09-22T10:00:00Z",
            "transcript": "notes",
        },
        headers=auth_header(token_a),
    )
    meeting_id = created.json()["id"]

    # Beta cannot see or fetch Acme's meeting
    assert (await client.get("/api/v1/meetings", headers=auth_header(token_b))).json() == []
    assert (
        await client.get(f"/api/v1/meetings/{meeting_id}", headers=auth_header(token_b))
    ).status_code == 404


async def _create_meeting(client: AsyncClient, token: str, client_id: str, title: str) -> str:
    resp = await client.post(
        "/api/v1/meetings",
        json={
            "client_id": client_id,
            "title": title,
            "occurred_at": "2026-09-22T10:00:00Z",
            "transcript": "notes",
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 202
    return resp.json()["id"]


async def test_list_meetings_filtered_by_client(
    client: AsyncClient, session: AsyncSession
) -> None:
    """?client_id=... scopes the list to one client; without it, all tenant meetings."""
    await seed_tenant_user(session, slug="acme", email="a@acme.com")
    token = await login(client, "acme", "a@acme.com")
    client_a = await _create_client(client, token, name="Client A")
    client_b = await _create_client(client, token, name="Client B")
    await _create_meeting(client, token, client_a, "A1")
    await _create_meeting(client, token, client_a, "A2")
    await _create_meeting(client, token, client_b, "B1")

    # No filter -> all three.
    all_resp = await client.get("/api/v1/meetings", headers=auth_header(token))
    assert len(all_resp.json()) == 3

    # Filtered to client A -> only A's two.
    a_resp = await client.get(
        "/api/v1/meetings", params={"client_id": client_a}, headers=auth_header(token)
    )
    a_meetings = a_resp.json()
    assert len(a_meetings) == 2
    assert {m["title"] for m in a_meetings} == {"A1", "A2"}
    assert all(m["client_id"] == client_a for m in a_meetings)


async def test_list_meetings_filter_cannot_cross_tenant(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Filtering by another tenant's client_id returns nothing (stays tenant-scoped)."""
    await seed_tenant_user(session, slug="acme", email="a@acme.com")
    await seed_tenant_user(session, slug="beta", email="b@beta.com")
    token_a = await login(client, "acme", "a@acme.com")
    token_b = await login(client, "beta", "b@beta.com")
    acme_client = await _create_client(client, token_a, name="Acme Client")
    await _create_meeting(client, token_a, acme_client, "A1")

    # Beta filters by Acme's client_id -> empty (tenant filter still applies).
    resp = await client.get(
        "/api/v1/meetings", params={"client_id": acme_client}, headers=auth_header(token_b)
    )
    assert resp.json() == []
