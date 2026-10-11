"""MCP Slice 1 tests: the auth boundary + the search_client_history tool.

The auth tests are pure (no DB) — they exercise the security-critical boundary: a tool call
is only honored with a valid bearer token, and the tenant is taken from the token.

The tool test wires the tool to the test MySQL + pgvector (same pattern as test_search) by
patching the session factory and vector store the tool uses.
"""

import uuid
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import NullPool, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import create_access_token
from app.integrations.embeddings.mock import MockEmbeddingProvider
from app.integrations.vectorstore.pgvector import VectorStore
from app.mcp import server as mcp_server
from app.mcp.auth import MCPAuthError, authenticate
from app.models.meetings import Meeting
from app.workers.index_worker import handle_intelligence_extracted
from tests.conftest import auth_header, login, seed_tenant_user

TEST_VECTOR_URL = "postgresql+asyncpg://clientlens:clientlens@localhost:5433/clientlens_vectors"
TRANSCRIPT = "The client wants to sell the business and plan tax and succession to their son. " * 10


def _ctx_with_auth(header_value: str | None):
    """Build a fake MCP Context whose request has (or lacks) an Authorization header."""
    headers = {"authorization": header_value} if header_value is not None else {}
    request = SimpleNamespace(headers=headers)
    request_context = SimpleNamespace(request=request)
    return SimpleNamespace(request_context=request_context)


# ---- auth boundary (no DB) ----

def test_authenticate_accepts_valid_token_and_takes_tenant_from_it() -> None:
    token = create_access_token(subject="u1", tenant_id="tenant-xyz", role="advisor")
    principal = authenticate(_ctx_with_auth(f"Bearer {token}"))
    assert principal.tenant_id == "tenant-xyz"
    assert principal.user_id == "u1"


def test_authenticate_rejects_missing_header() -> None:
    with pytest.raises(MCPAuthError):
        authenticate(_ctx_with_auth(None))


def test_authenticate_rejects_malformed_header() -> None:
    with pytest.raises(MCPAuthError):
        authenticate(_ctx_with_auth("Basic abc"))


def test_authenticate_rejects_garbage_token() -> None:
    with pytest.raises(MCPAuthError):
        authenticate(_ctx_with_auth("Bearer not-a-jwt"))


# ---- the tool, end to end (needs MySQL + pgvector) ----

@pytest_asyncio.fixture(loop_scope="session")
async def vstore():
    engine = create_async_engine(TEST_VECTOR_URL, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            await conn.execute(select(1))
    except (OperationalError, OSError) as exc:  # pragma: no cover
        await engine.dispose()
        pytest.skip(f"pgvector not reachable ({exc})")
    yield VectorStore(engine)
    await engine.dispose()


async def test_search_tool_returns_grounded_answer_for_authenticated_tenant(
    client, session, engine, vstore, monkeypatch
) -> None:
    tenant, _ = await seed_tenant_user(session, slug="acme", email="a@acme.com")
    token = await login(client, "acme", "a@acme.com")
    cid = (await client.post("/api/v1/clients", json={"name": "John"},
                             headers=auth_header(token))).json()["id"]
    await client.post(
        "/api/v1/meetings",
        json={"client_id": cid, "title": "R", "occurred_at": "2026-09-22T10:00:00Z",
              "transcript": TRANSCRIPT},
        headers=auth_header(token),
    )

    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        m = (await s.execute(select(Meeting))).scalars().first()
    async with maker() as s:
        await handle_intelligence_extracted(
            s, MockEmbeddingProvider(), vstore,
            event_id=str(uuid.uuid4()),
            payload={"meeting_id": m.id, "tenant_id": m.tenant_id, "client_id": m.client_id},
        )

    # Point the tool at the TEST databases: its session factory -> test engine; its
    # VectorStore -> the test pgvector (port 5433); embedder -> mock (matches indexing).
    monkeypatch.setattr(mcp_server, "SessionLocal", maker)
    monkeypatch.setattr(mcp_server, "VectorStore", lambda: vstore)
    monkeypatch.setattr(mcp_server, "get_embedding_provider", lambda: MockEmbeddingProvider())

    # Authenticated as this tenant -> grounded answer.
    jwt_token = create_access_token(subject="u1", tenant_id=tenant.id, role="advisor")
    ctx = _ctx_with_auth(f"Bearer {jwt_token}")
    out = await mcp_server.search_client_history(ctx, query="selling the business and taxes",
                                                 client_id=cid)
    assert "Sources:" in out
    assert m.id in out

    # Unauthenticated -> refused, no data.
    denied = await mcp_server.search_client_history(_ctx_with_auth(None),
                                                    query="anything")
    assert denied.startswith("Unauthorized")

    await vstore.delete_by_meeting(m.tenant_id, m.id)
