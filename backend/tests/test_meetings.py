"""Meeting CRUD + tenant-isolation tests."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_header, login, seed_tenant_user


async def _create_client(client: AsyncClient, token: str, name: str = "John Smith") -> str:
    resp = await client.post("/api/v1/clients", json={"name": name}, headers=auth_header(token))
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_create_meeting_processes_to_completed(
    client: AsyncClient, session: AsyncSession
) -> None:
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
    assert resp.status_code == 201
    body = resp.json()
    # Synchronous processing ran inline, so the status is already COMPLETED on return.
    assert body["status"] == "COMPLETED"
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
