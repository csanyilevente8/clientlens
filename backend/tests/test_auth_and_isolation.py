"""Auth and tenant-isolation tests (the ADR-008 backstop).

These run against a real MySQL test DB via the fixtures in conftest.py.
"""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_header, login, seed_tenant_user


async def test_login_success_returns_token(client: AsyncClient, session: AsyncSession) -> None:
    await seed_tenant_user(session, slug="acme", email="a@acme.com")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"tenant_slug": "acme", "email": "a@acme.com", "password": "secret123"},
    )
    assert resp.status_code == 200
    assert resp.json()["token_type"] == "bearer"
    assert resp.json()["access_token"]


async def test_login_wrong_password_401(client: AsyncClient, session: AsyncSession) -> None:
    await seed_tenant_user(session, slug="acme", email="a@acme.com")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"tenant_slug": "acme", "email": "a@acme.com", "password": "WRONG"},
    )
    assert resp.status_code == 401


async def test_login_unknown_tenant_401(client: AsyncClient, session: AsyncSession) -> None:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"tenant_slug": "nope", "email": "a@acme.com", "password": "secret123"},
    )
    assert resp.status_code == 401


async def test_clients_endpoint_requires_auth(client: AsyncClient) -> None:
    # No Authorization header -> 401 (protection is transitive through the repo dependency).
    resp = await client.get("/api/v1/clients")
    assert resp.status_code == 401


async def test_tenant_cannot_see_or_touch_other_tenants_client(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The core ADR-008 guarantee: tenant B cannot read or delete tenant A's data."""
    await seed_tenant_user(session, slug="acme", email="a@acme.com")
    await seed_tenant_user(session, slug="beta", email="b@beta.com")
    token_a = await login(client, "acme", "a@acme.com")
    token_b = await login(client, "beta", "b@beta.com")

    # Acme creates a client
    created = await client.post(
        "/api/v1/clients", json={"name": "John Smith"}, headers=auth_header(token_a)
    )
    assert created.status_code == 201
    client_id = created.json()["id"]

    # Beta cannot list it
    beta_list = await client.get("/api/v1/clients", headers=auth_header(token_b))
    assert beta_list.status_code == 200
    assert beta_list.json() == []

    # Beta cannot GET it by id
    assert (
        await client.get(f"/api/v1/clients/{client_id}", headers=auth_header(token_b))
    ).status_code == 404

    # Beta cannot DELETE it
    assert (
        await client.delete(f"/api/v1/clients/{client_id}", headers=auth_header(token_b))
    ).status_code == 404

    # Acme's client still exists after Beta's attempts
    assert (
        await client.get(f"/api/v1/clients/{client_id}", headers=auth_header(token_a))
    ).status_code == 200
