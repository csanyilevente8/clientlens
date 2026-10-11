# 07 — MCP → RAG flow & MCP server architecture

How an external reasoning model (Claude) reaches ClientLens's client intelligence through
the MCP server, and how the request flows through the service layer to the data stores and
the (internal) LLM. See also `ADR-006` (mcp-application-boundary), SYSTEMDESING §19.

## The one rule that shapes everything

The MCP server is an **application-layer boundary** (SYSTEMDESING §19): it **never touches
MySQL or the vector store directly**. Every tool goes through the service/repository layer,
so authorization, tenant isolation, validation, and auditing live in one place — the same
guarantees as the REST path.

## Architecture / request flow

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  EXTERNAL REASONING MODEL  (the MCP CLIENT)                                        │
│  e.g. Claude Desktop / an app embedding an MCP client.                             │
│  User: "What are Jane's open action items?"  → the model picks a tool to call.     │
└──────────────────────────────┬─────────────────────────────────────────────────────┘
                                │ MCP protocol (JSON-RPC 2.0) over HTTP/SSE
                                │ POST /sse  ·  Authorization: Bearer <JWT>
                                │ tools/call { name, arguments }
                                ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│  MCP SERVER  (app/mcp/)  — APPLICATION BOUNDARY                                    │
│  FastMCP, ASGI via sse_app(), run under uvicorn                                     │
│                                                                                    │
│   _run_tool(ctx, tool_name, args, work):   ← shared runner for ALL tools           │
│     1. AUTH (auth.py): read "Bearer <jwt>" → decode_access_token (RS256,           │
│        PUBLIC key, ADR-009) → principal{ tenant_id, user_id }                      │
│        tenant_id comes ONLY from the token, never from a tool argument             │
│        on failure → audit "unauthorized" (no tenant) → return "Unauthorized"       │
│     2. WORK: run the tenant-scoped tool body against a fresh DB session            │
│     3. AUDIT (audit.py): write mcp_audit_logs row (success|error|unauthorized),    │
│        own committed session → durable (§772)                                      │
│                                                                                    │
│   Tools (read-only, §19):                                                          │
│     • search_client_history(query, client_id?)  → RetrievalService (RAG)           │
│     • get_client_context(client_id)             → ClientGoal / ClientConcern        │
│     • get_recent_meetings(client_id, limit)     → Meeting (tenant+client scoped)    │
│     • get_open_action_items(client_id)          → ActionItem                        │
└──────────────────────────────┬─────────────────────────────────────────────────────┘
                                │ service / repository call (tenant_id from token)
                                ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│  SERVICE / REPOSITORY LAYER                                                        │
│                                                                                    │
│  RetrievalService (RAG orchestrator — the SAME one the REST /search uses):         │
│     1 embed query      → EmbeddingProvider (factory: mock | real)                  │
│     2 semantic search  → VectorStore (pgvector, tenant-scoped, top-k)              │
│     3 structured ctx   → MySQL intelligence tables (goals/concerns, tenant-scoped) │
│     4 assemble bounded context (chunks + structured)                               │
│     5 answer grounded  → LLMProvider (factory: mock | Anthropic)                   │
│                                                                                    │
│  Structured tools: tenant-scoped SELECTs over intelligence / meetings tables.      │
└───────┬───────────────────────┬───────────────────────┬───────────────────┬───────┘
        ▼                       ▼                       ▼                   ▼
┌───────────────┐   ┌────────────────────┐   ┌────────────────────┐  ┌──────────────────┐
│ Embedding     │   │ VectorStore        │   │ MySQL (ORM)        │  │ LLMProvider      │
│ Provider      │   │ pgvector           │   │ clients, meetings, │  │ mock (dev) /     │
│ mock | real   │   │ transcript_chunks  │   │ intelligence,      │  │ Anthropic (prod) │
│               │   │ tenant-scoped NN   │   │ mcp_audit_logs     │  │ answer_question  │
│               │   │ (ADR-004/008)      │   │ (ADR-008)          │  │        │         │
└───────────────┘   └────────────────────┘   └────────────────────┘  └────────┼─────────┘
                                                                               ▼ (prod)
                                                              ┌────────────────────────────┐
                                                              │ Anthropic Claude API        │
                                                              │ (the INTERNAL answer model) │
                                                              └────────────────────────────┘

      ◄──────── result (text) flows back up: tool → tools/call result → HTTP/SSE ────────►
      the external model weaves the answer + sources into its reply to the user.
```

## Key points

- **Two LLMs, different roles.** The model at the *top* is the MCP **client** — it decides
  which tool to call and consumes the result. The `LLMProvider` at the *bottom* is the
  **internal** model that generates the grounded RAG answer inside `RetrievalService`
  (`search_client_history` only). Both may be "Claude", at different layers.
- **Tenant isolation is defense-in-depth.** `tenant_id` is derived once at the MCP boundary
  (from the token) and re-enforced at every data access: the vector search filters by tenant
  (ADR-004/008) and every MySQL query filters by tenant. A tool can't reach another tenant's
  data even if a client_id from another tenant is passed — it simply matches nothing.
- **Auth is per request (HTTP/SSE).** Each `tools/call` carries its own bearer JWT; the MCP
  server verifies it with the public key (ADR-009) and never holds the signing key.
- **Everything is audited, durably.** `_run_tool` writes an `mcp_audit_logs` row for every
  call — success, error, or unauthorized — in its own committed session (§772). Auth
  failures record no tenant_id (nothing leaked).
- **Self-describing tools.** Each tool's name + docstring + argument schema is advertised via
  `tools/list`; the external model discovers and calls them with no per-tool glue code on the
  integrator's side (the value of MCP).
- **Reuse, not reimplementation.** `search_client_history` calls the exact `RetrievalService`
  behind REST `/search`, so the MCP answer and the REST answer are identical.

## Integration (how someone connects)

HTTP/SSE transport: point an MCP client at the server's `/sse` endpoint with a bearer token:

```json
{
  "mcpServers": {
    "clientlens": {
      "url": "https://<host>/sse",
      "headers": { "Authorization": "Bearer <advisor JWT>" }
    }
  }
}
```
Run the server: `uv run uvicorn app.mcp.server:app --port 9100`.
