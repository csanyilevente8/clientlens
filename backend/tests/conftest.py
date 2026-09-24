"""Shared test fixtures.

Strategy: run against a REAL MySQL test database (matches what we ship — important for a
security test like tenant isolation). Tables are created once per session and truncated
between tests. The app's get_session dependency is overridden to use the test session.

Requires MySQL running (docker compose up -d mysql). The test DB is created if missing.
"""

from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.db import Base, get_session
from app.core.security import hash_password
from app.main import create_app
from app.models.roles import Role
from app.models.tenants import Tenant
from app.models.users import User

settings = get_settings()
# A dedicated test database so we never touch dev data.
TEST_DB_URL = settings.database_url.rsplit("/", 1)[0] + "/clientlens_test"


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def engine():
    # The test database (clientlens_test) is created + granted by the MySQL init script.
    # Create tables once for the session; drop them at the end. Between tests we TRUNCATE.
    eng = create_async_engine(TEST_DB_URL, poolclass=NullPool)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


async def _truncate_all(engine) -> None:
    async with engine.begin() as conn:
        await conn.exec_driver_sql("SET FOREIGN_KEY_CHECKS=0")
        for table in reversed(Base.metadata.sorted_tables):
            await conn.exec_driver_sql(f"TRUNCATE TABLE {table.name}")
        await conn.exec_driver_sql("SET FOREIGN_KEY_CHECKS=1")


@pytest_asyncio.fixture(loop_scope="session")
async def session(engine) -> AsyncGenerator[AsyncSession, None]:
    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await _truncate_all(engine)


@pytest_asyncio.fixture(loop_scope="session")
async def client(engine) -> AsyncGenerator[AsyncClient, None]:
    """httpx client wired to the app, with get_session overridden to the test DB."""
    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with maker() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def seed_tenant_user(
    session: AsyncSession, *, slug: str, email: str, password: str = "secret123"
) -> tuple[Tenant, User]:
    """Insert a tenant + advisor user; return them."""
    tenant = Tenant(name=slug.title(), slug=slug)
    session.add(tenant)
    await session.flush()
    user = User(
        tenant_id=tenant.id,
        email=email,
        role=Role.ADVISOR,
        hashed_password=hash_password(password),
    )
    session.add(user)
    await session.commit()
    return tenant, user


async def login(client: AsyncClient, slug: str, email: str, password: str = "secret123") -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"tenant_slug": slug, "email": email, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
