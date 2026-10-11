"""ClientLens MCP server (Phase 6, SYSTEMDESIGN §19).

Exposes READ-ONLY client-intelligence tools to an external reasoning model (Claude) over
MCP (HTTP/SSE transport). The server is an APPLICATION-LAYER BOUNDARY: it never touches
MySQL/pgvector directly — every tool goes through a service/repository, so authorization,
tenant isolation, validation, and auditing all live in one place.

Every tool runs through `_run_tool`, which: (1) authenticates the bearer token and derives
the tenant from it, (2) runs the tenant-scoped work, (3) writes a durable audit row for the
outcome (success / error / unauthorized). This keeps all tools consistent.

Run (networked, bearer-token per request):
    uv run uvicorn app.mcp.server:app --port 9100
The MCP endpoint is served at /sse; clients connect with `Authorization: Bearer <jwt>`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from mcp.server.fastmcp import Context, FastMCP
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.integrations.embeddings.factory import get_embedding_provider
from app.integrations.llm.factory import get_llm_provider
from app.integrations.vectorstore.pgvector import VectorStore
from app.mcp.audit import record_tool_call
from app.mcp.auth import MCPAuthError, McpPrincipal, authenticate
from app.models.intelligence import ActionItem, ClientConcern, ClientGoal
from app.models.meetings import Meeting
from app.services.retrieval import RetrievalService

mcp = FastMCP(
    "clientlens",
    instructions=(
        "Read-only access to an advisor's client intelligence: meeting history, extracted "
        "goals/concerns/action items, and semantic Q&A grounded in meeting transcripts. "
        "All results are scoped to the authenticated advisor's tenant."
    ),
)

# A tool body: given a DB session and the authenticated principal, return a text result.
ToolWork = Callable[[AsyncSession, McpPrincipal], Awaitable[str]]


async def _run_tool(ctx: Context, tool_name: str, arguments: dict, work: ToolWork) -> str:
    """Shared tool runner: authenticate -> run tenant-scoped work -> audit the outcome.

    Centralizes the boundary concerns (SYSTEMDESIGN §19) so every tool is consistent:
    tenant comes only from the token; the work gets its own DB session; and every call —
    including auth failures — is recorded in the durable audit log (§772).
    """
    try:
        principal = authenticate(ctx)
    except MCPAuthError as exc:
        await record_tool_call(
            tool_name=tool_name, arguments=arguments,
            tenant_id=None, user_id=None, outcome="unauthorized", error=str(exc),
        )
        return f"Unauthorized: {exc}"

    try:
        async with SessionLocal() as session:
            output = await work(session, principal)
    except Exception as exc:  # noqa: BLE001 — audit the failure, surface a clean message
        await record_tool_call(
            tool_name=tool_name, arguments=arguments,
            tenant_id=principal.tenant_id, user_id=principal.user_id,
            outcome="error", error=str(exc),
        )
        return f"Error: {exc}"

    await record_tool_call(
        tool_name=tool_name, arguments=arguments,
        tenant_id=principal.tenant_id, user_id=principal.user_id, outcome="success",
    )
    return output


@mcp.tool()
async def search_client_history(ctx: Context, query: str, client_id: str | None = None) -> str:
    """Answer a natural-language question about a client's history.

    Grounded (RAG) in the advisor's meeting transcripts and extracted intelligence.
    Optionally scope to one client via `client_id`.

    Args:
        query: the natural-language question.
        client_id: optional client to scope the search to.
    """
    async def work(session: AsyncSession, principal: McpPrincipal) -> str:
        service = RetrievalService(
            session=session,
            embedder=get_embedding_provider(),
            store=VectorStore(),
            llm=get_llm_provider(),
        )
        result = await service.answer(
            tenant_id=principal.tenant_id, query=query, client_id=client_id,
        )
        srcs = "\n".join(f"- (meeting {s.meeting_id}) {s.content[:160]}" for s in result.sources)
        return f"{result.answer}\n\nSources:\n{srcs}" if srcs else result.answer

    return await _run_tool(ctx, "search_client_history",
                           {"query": query, "client_id": client_id}, work)


@mcp.tool()
async def get_client_context(ctx: Context, client_id: str) -> str:
    """Return a client's extracted context: goals and concerns.

    A compact summary pulled from the structured intelligence tables for one client.

    Args:
        client_id: the client to summarize.
    """
    async def work(session: AsyncSession, principal: McpPrincipal) -> str:
        goals = (await session.execute(
            select(ClientGoal).where(
                ClientGoal.tenant_id == principal.tenant_id,
                ClientGoal.client_id == client_id,
            )
        )).scalars().all()
        concerns = (await session.execute(
            select(ClientConcern).where(
                ClientConcern.tenant_id == principal.tenant_id,
                ClientConcern.client_id == client_id,
            )
        )).scalars().all()
        if not goals and not concerns:
            return "No extracted context found for this client."
        lines = []
        if goals:
            lines.append("Goals:")
            lines += [f"- {g.description}" + (f" ({g.timeframe})" if g.timeframe else "")
                      for g in goals]
        if concerns:
            lines.append("Concerns:")
            lines += [f"- {c.description}" for c in concerns]
        return "\n".join(lines)

    return await _run_tool(ctx, "get_client_context", {"client_id": client_id}, work)


@mcp.tool()
async def get_recent_meetings(ctx: Context, client_id: str, limit: int = 5) -> str:
    """List a client's most recent meetings (title, date, processing status).

    Args:
        client_id: the client whose meetings to list.
        limit: max number of meetings to return (default 5).
    """
    async def work(session: AsyncSession, principal: McpPrincipal) -> str:
        rows = (await session.execute(
            select(Meeting)
            .where(Meeting.tenant_id == principal.tenant_id, Meeting.client_id == client_id)
            .order_by(Meeting.occurred_at.desc())
            .limit(max(1, min(limit, 50)))
        )).scalars().all()
        if not rows:
            return "No meetings found for this client."
        return "\n".join(
            f"- {m.occurred_at:%Y-%m-%d} · {m.title} · {m.status.value}" for m in rows
        )

    return await _run_tool(ctx, "get_recent_meetings",
                           {"client_id": client_id, "limit": limit}, work)


@mcp.tool()
async def get_open_action_items(ctx: Context, client_id: str) -> str:
    """List the action items extracted for a client across their meetings.

    Args:
        client_id: the client whose action items to list.
    """
    async def work(session: AsyncSession, principal: McpPrincipal) -> str:
        items = (await session.execute(
            select(ActionItem).where(
                ActionItem.tenant_id == principal.tenant_id,
                ActionItem.client_id == client_id,
            )
        )).scalars().all()
        if not items:
            return "No action items found for this client."
        return "\n".join(
            f"- {a.description}" + (f" (owner: {a.owner})" if a.owner else "") for a in items
        )

    return await _run_tool(ctx, "get_open_action_items", {"client_id": client_id}, work)


# ASGI app for the HTTP/SSE transport — run with uvicorn.
app = mcp.sse_app()
