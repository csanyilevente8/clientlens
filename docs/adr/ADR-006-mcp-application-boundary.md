# Decision

The MCP server is an **application-layer boundary**: it exposes high-level, read-only tools
to an external reasoning model and **always goes through the service/repository layer — never
directly to MySQL or the vector store**. Every tool call authenticates (bearer JWT), derives
the tenant from the verified token, and is recorded in a durable audit log.

## Context

The headline product scenario (SPEC) is "ask an external AI assistant (Claude) questions
about clients through MCP." MCP lets an external model discover and call our tools. The
tempting shortcut is to let those tools read the database directly for speed/simplicity. But
MCP calls originate **outside** the application's normal auth/validation path, so a direct-DB
MCP server would bypass every protection the REST path enforces.

## Requirements

- Expose read-only client-intelligence capabilities to an external model (SYSTEMDESING §19).
- Enforce the **same tenant isolation** as the rest of the system (ADR-008): a tool call can
  never read another tenant's data.
- Authenticate every call; the external model is not a logged-in advisor by default.
- Audit every call durably (SYSTEMDESING §772 lists audit as Durable) — "MCP requests are
  audited" is a Definition-of-Done item.
- Reuse existing business logic (retrieval/RAG, repositories) rather than reimplementing it.

## Options

1. **MCP tools call the application/service layer** (chosen). Tools wrap `RetrievalService`
   and the tenant-scoped repositories; auth + audit live in the MCP boundary.
2. **MCP server queries MySQL/pgvector directly.** Rejected — bypasses authorization, tenant
   isolation, validation, rate limiting, auditing, and duplicates business rules; the exact
   anti-pattern SYSTEMDESING §19 warns against.
3. **Expose the REST API to the model instead of MCP.** Rejected — REST is not the MCP
   protocol; the model cannot discover/compose REST endpoints as tools the way MCP enables
   (self-describing tools, no per-tool glue for the integrator).

## Why

Routing through the service layer puts authorization, tenant isolation, validation, and
auditing in **one place**, shared with the REST path. The tenant comes only from the verified
JWT (ADR-009 verifies with the public key), never from a tool argument — so isolation is
structural. Reusing `RetrievalService` means the MCP RAG answer is identical to the REST
`/search` answer. Transport is **HTTP/SSE** so each request carries its own bearer token
(per-request authorization), suitable for a networked, multi-caller service.

## Trade-offs

- A thin indirection (tool → service) costs a little latency vs. a raw query — negligible,
  and worth it for the shared guarantees.
- MCP tools are not FastAPI requests, so there is no request-scoped DI: each tool opens its
  own DB session. Minor extra boilerplate, centralized in a `_run_tool` runner.
- Audit writes are synchronous (own committed session) — a small cost per call, accepted
  because the audit trail must be durable.
- SDK: pinned `mcp>=1.2,<2` (the stable `FastMCP` line). 2.x renamed `FastMCP→MCPServer` with
  breaking API changes and little documentation; revisit when 2.x matures.

## Failure modes

- **Missing / invalid / expired token** → the tool returns "Unauthorized", records an audit
  row with `outcome=unauthorized` and **no tenant_id** (nothing leaked), and does no work.
- **Downstream error** (DB/vector/LLM) → caught at the boundary, audited as `outcome=error`
  with the message, and a clean "Error: ..." is returned to the model (no stack trace leak).
- **Cross-tenant attempt** (a tool arg referencing another tenant's client) → impossible to
  satisfy: every query filters by the token's tenant, so it simply returns nothing.
- **Audit write fails** → surfaces as a tool error; the audit path is kept simple (single
  insert + commit) to minimize this risk.

## Consequences

The MCP server is a controlled boundary with the same security posture as the REST API.
Adding a tool = a new function wrapping a service, auto-audited and auth-gated via the shared
runner — no new integration code for callers (self-describing tools). The audit log gives a
durable record of every external-model access to client data.

## When we would reconsider this decision

- If a read path proves too slow through the service layer *and* profiling shows the
  indirection (not the DB) is the bottleneck — we would still not go direct-to-DB, but might
  add a caching layer in the service (ADR-007).
- If we needed **write** capabilities via MCP — that would require revisiting authorization
  (currently read-only) and likely a different approval/audit model.
- If the MCP SDK 2.x (`MCPServer`) becomes the stable, documented norm — revisit the pin.
