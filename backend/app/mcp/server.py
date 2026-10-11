"""ClientLens MCP server (Phase 6, SYSTEMDESIGN §19).

Exposes READ-ONLY client-intelligence tools to an external reasoning model (Claude) over
MCP (HTTP/SSE transport). The server is an APPLICATION-LAYER BOUNDARY: it never touches
MySQL/pgvector directly — every tool goes through a service (here RetrievalService), so
authorization, tenant isolation, validation, and (Slice 2) auditing all live in one place.

Run (networked, bearer-token per request):
    uv run uvicorn app.mcp.server:app --port 9100
The MCP endpoint is served at /sse; clients connect with `Authorization: Bearer <jwt>`.
"""

from __future__ import annotations

from mcp.server.fastmcp import Context, FastMCP

from app.core.db import SessionLocal
from app.integrations.embeddings.factory import get_embedding_provider
from app.integrations.llm.factory import get_llm_provider
from app.integrations.vectorstore.pgvector import VectorStore
from app.mcp.audit import record_tool_call
from app.mcp.auth import MCPAuthError, authenticate
from app.services.retrieval import RetrievalService

mcp = FastMCP(
    "clientlens",
    instructions=(
        "Read-only access to an advisor's client intelligence: meeting history, extracted "
        "goals/concerns/action items, and semantic Q&A grounded in meeting transcripts. "
        "All results are scoped to the authenticated advisor's tenant."
    ),
)


@mcp.tool()
async def search_client_history(ctx: Context, query: str, client_id: str | None = None) -> str:
    """Answer a natural-language question about a client's history.

    The answer is grounded (RAG) in the advisor's meeting transcripts and extracted
    intelligence. Optionally scope to a single client via `client_id`; otherwise searches
    across the tenant's clients.

    Args:
        query: the natural-language question.
        client_id: optional client to scope the search to.
    """
    # 1) Authenticate per request; tenant comes ONLY from the verified token (§19/ADR-008).
    args = {"query": query, "client_id": client_id}
    try:
        principal = authenticate(ctx)
    except MCPAuthError as exc:
        await record_tool_call(
            tool_name="search_client_history", arguments=args,
            tenant_id=None, user_id=None, outcome="unauthorized", error=str(exc),
        )
        return f"Unauthorized: {exc}"

    # 2) Go through the service layer, never the DB directly. MCP tools are not FastAPI
    #    requests, so we open our own session (there is no request-scoped DI here).
    try:
        async with SessionLocal() as session:
            service = RetrievalService(
                session=session,
                embedder=get_embedding_provider(),
                store=VectorStore(),
                llm=get_llm_provider(),
            )
            result = await service.answer(
                tenant_id=principal.tenant_id,  # from the token, never from args
                query=query,
                client_id=client_id,
            )
    except Exception as exc:  # noqa: BLE001 — audit the failure, surface a clean message
        await record_tool_call(
            tool_name="search_client_history", arguments=args,
            tenant_id=principal.tenant_id, user_id=principal.user_id,
            outcome="error", error=str(exc),
        )
        return f"Error: {exc}"

    # 3) Audit the successful call, then return a text result the model can read.
    await record_tool_call(
        tool_name="search_client_history", arguments=args,
        tenant_id=principal.tenant_id, user_id=principal.user_id, outcome="success",
    )
    sources = "\n".join(f"- (meeting {s.meeting_id}) {s.content[:160]}" for s in result.sources)
    return f"{result.answer}\n\nSources:\n{sources}" if sources else result.answer


# ASGI app for the HTTP/SSE transport — run with uvicorn.
app = mcp.sse_app()
