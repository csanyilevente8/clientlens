"""MCP Slice 1 tests: the auth boundary + the search_client_history tool.

The auth tests are pure (no DB) — they exercise the security-critical boundary: a tool call
is only honored with a valid bearer token, and the tenant is taken from the token.

The tool test wires the tool to the test MySQL + pgvector (same pattern as test_search) by
patching the session factory and vector store the tool uses.
"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import NullPool, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import create_access_token
from app.integrations.embeddings.mock import MockEmbeddingProvider
from app.integrations.vectorstore.pgvector import VectorStore
from app.mcp import audit as mcp_audit
from app.mcp import server as mcp_server
from app.mcp.auth import MCPAuthError, authenticate
from app.models.mcp_audit import McpAuditLog
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
    # Also point the audit recorder at the test DB.
    monkeypatch.setattr(mcp_server, "SessionLocal", maker)
    monkeypatch.setattr(mcp_server, "VectorStore", lambda: vstore)
    monkeypatch.setattr(mcp_server, "get_embedding_provider", lambda: MockEmbeddingProvider())
    monkeypatch.setattr(mcp_audit, "SessionLocal", maker)

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

    # Both calls were audited (durable, §772): one success + one unauthorized.
    async with maker() as s:
        logs = (await s.execute(select(McpAuditLog))).scalars().all()
    outcomes = sorted(a.outcome for a in logs)
    assert outcomes == ["success", "unauthorized"]
    success = next(a for a in logs if a.outcome == "success")
    assert success.tenant_id == tenant.id
    assert success.tool_name == "search_client_history"
    assert success.arguments["client_id"] == cid
    unauth = next(a for a in logs if a.outcome == "unauthorized")
    assert unauth.tenant_id is None  # no tenant leaked for a failed-auth call

    await vstore.delete_by_meeting(m.tenant_id, m.id)


# ---- the structured tools (need MySQL only, no pgvector) ----

async def test_structured_tools_return_tenant_scoped_data_and_audit(
    client, session, engine, monkeypatch
) -> None:
    from app.models.clients import Client
    from app.models.intelligence import ActionItem, ClientConcern, ClientGoal

    tenant, _ = await seed_tenant_user(session, slug="acme", email="a@acme.com")
    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    # Seed a client + a meeting + some extracted intelligence directly.
    async with maker() as s:
        c = Client(tenant_id=tenant.id, name="Jane")
        s.add(c)
        await s.flush()
        cid = c.id
        meeting = Meeting(tenant_id=tenant.id, client_id=cid, title="Annual Review",
                          occurred_at=datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
                          transcript="notes")
        s.add(meeting)
        await s.flush()
        mid = meeting.id
        s.add(ClientGoal(tenant_id=tenant.id, client_id=cid, meeting_id=mid,
                         description="Retire by 60", timeframe="5 years"))
        s.add(ClientConcern(tenant_id=tenant.id, client_id=cid, meeting_id=mid,
                            description="Market volatility"))
        s.add(ActionItem(tenant_id=tenant.id, client_id=cid, meeting_id=mid,
                         description="Send tax projection", owner="advisor"))
        await s.commit()

    monkeypatch.setattr(mcp_server, "SessionLocal", maker)
    monkeypatch.setattr(mcp_audit, "SessionLocal", maker)

    token = create_access_token(subject="u1", tenant_id=tenant.id, role="advisor")
    ctx = _ctx_with_auth(f"Bearer {token}")

    context = await mcp_server.get_client_context(ctx, client_id=cid)
    assert "Retire by 60" in context and "Market volatility" in context

    meetings = await mcp_server.get_recent_meetings(ctx, client_id=cid)
    assert "Annual Review" in meetings and "2026-09-01" in meetings

    actions = await mcp_server.get_open_action_items(ctx, client_id=cid)
    assert "Send tax projection" in actions and "advisor" in actions

    # Unauthenticated is refused for a structured tool too.
    denied = await mcp_server.get_client_context(_ctx_with_auth(None), client_id=cid)
    assert denied.startswith("Unauthorized")

    # All four calls audited (3 success + 1 unauthorized), tenant scoped.
    async with maker() as s:
        logs = (await s.execute(select(McpAuditLog))).scalars().all()
    by_tool = {a.tool_name for a in logs if a.outcome == "success"}
    assert by_tool == {"get_client_context", "get_recent_meetings", "get_open_action_items"}
    assert any(a.outcome == "unauthorized" and a.tenant_id is None for a in logs)
