# ClientLens — Progress

Detailed, versioned progress for this repo. The workspace-level entry point is
`../WORKSPACE.md` (one level up, outside git). Read that first, then this.

> **Project goal (per `../SYSTEMDESING.md`):** this is a **system-design learning
> project**. Deliverables = working app **+** system-design portfolio (`docs/adr/`,
> `docs/architecture/`, `docs/capacity/`, `docs/failure-scenarios/`,
> `docs/interview-questions/`). Method: reason Requirement → Constraint → Options →
> Decision → Trade-off → Failure mode → Scaling (SYSTEMDESING §2). Build simple/synchronous
> first, observe the bottleneck, then justify async (Kafka + outbox) with ADRs.
> New scope vs original SPEC: transactional outbox (§10), capacity estimation (§4),
> failure matrix + injection exercises (§21/§28), idempotency keys on POST (§24), MCP must
> not touch MySQL directly (§19), consistency classification (§17).

---

## Current phase

**Phase 1 (Foundation) — in progress.**
Done: backend skeleton (FastAPI app factory, Pydantic settings, `/health`), uv + Python
3.12 pinned, pytest passing, ruff clean. MySQL 8 wired via docker-compose; SQLAlchemy
(async) + Alembic set up; `/ready` readiness endpoint pings the DB and returns 200 with
the stack up. `docker compose up` starts MySQL + backend. Domain models done: Tenant
(+ unique slug), User (role enum, tenant FK, per-tenant unique email), Client (tenant FK)
— all migrated + verified; naming convention on Base.metadata. Shared mixin.
**Auth complete:** RS256 JWT + bcrypt (security.py), login endpoint (slug+email+password
-> token, uniform 401), current-user dependency (deps.py, stateless), protected /me — all
tested end-to-end. ADR-008 (multi-tenancy), ADR-009 (auth). Dev seed script.
Next in Phase 1: tenant-scoped repository layer (ADR-008 Approach B), then refactor login
+ clients CRUD through it, meetings CRUD (synchronous first per §5), frontend skeleton.
9 local commits, NOT pushed (holding per user).

Repository + clients CRUD DONE (ADR-008 Approach B): TenantScopedRepository[ModelT] base
injects tenant filter on every op; ClientRepository; get_client_repository dependency binds
tenant from CurrentUser; clients CRUD endpoints hold no tenant logic. Integration tests
(real MySQL test DB, NullPool, fixtures) incl. the tenant-isolation backstop.
Meetings CRUD DONE (SYNCHRONOUS, §5 Stage 1): Meeting model, MeetingRepository, create runs
processing inline. Bottleneck analysis DONE (docs/capacity + docs/failure-scenarios):
peak ~10/s, Little's Law -> ~200 concurrent -> worker-pool exhaustion; justifies async.
Phase 2 DONE (ADR-010): LLMProvider abstraction (mock default, keyword-based), MeetingAnalysis
schema, 5 intelligence tables w/ provenance, analyze_meeting service (validate->persist,
invalid->FAILED), GET /meetings/{id}/intelligence. §48 demo verified. Still synchronous.
14 tests passing. **PUSHED to origin/main** (18 commits).
Phase 3 (async) DONE — all 5 slices:
- Slice 1: transactional outbox (ADR §10) — meeting + outbox_event committed atomically,
  POST returns 202 CREATED (no inline analysis).
- Slice 2: Kafka (KRaft) + EventBus abstraction + polling outbox publisher.
- Slice 3: ai_worker consumes meeting.created; idempotent (processed_events UNIQUE +
  atomic marker; IntegrityError rollback on concurrent dup).
- Slice 4: worker retries (backoff+jitter, rollback+re-fetch) + DLQ topic on exhaustion
  (meeting FAILED + terminal marker).
- Slice 5: publisher + ai-worker run as compose services; VERIFIED live end-to-end
  against real Kafka; failure exercises D (worker crash) & E (Kafka down) pass — nothing
  lost, self-heals. Dockerfile generates dev JWT keys in-image.
20 tests passing. docs/failure-scenarios updated with executed exercises.
Phase 4 (Search/RAG) DONE — 3 slices:
- Slice 1: EmbeddingProvider abstraction (deterministic mock, dim 384) + pgvector
  container (ADR-004, host port 5433) + VectorStore (tenant-scoped NN search, cosine).
- Slice 2: chunker + index_worker (2nd Kafka consumer, consumer_name=index_worker);
  AI worker emits IntelligenceExtracted via outbox; cross-store idempotency (§25) —
  idempotent delete+add before the MySQL marker commit.
- Slice 3: RetrievalService (embed query -> tenant-scoped pgvector NN + structured data
  from MySQL -> RAG answer via llm.answer_question); POST /api/v1/search.
- VERIFIED live end-to-end: meeting -> analyze -> index -> search returns grounded answer
  + sources with scores. 23 tests passing.

Frontend (Phase 1 leftover) STARTED — mentor mode (developer writes code, assistant
explains/reviews):
- Vite + React 18 + TS + React Router + TanStack Query scaffold; dev proxy /api->:8000;
  @->src alias in BOTH tsconfig (type-checker) and vite.config (bundler).
- src/auth/token.ts (localStorage get/set/clear), src/api/client.ts (apiFetch<T> + apiGet/
  apiPost, JWT header, backend detail in errors).
- Login page (controlled form -> POST login -> setToken -> navigate; error display).
- Clients page: Client type, useClients() (useQuery), ClientsPage (loading/error/data),
  /clients route behind RequireAuth guard. Verified in browser.
- create-client form (useCreateClient useMutation + ["clients"] invalidation).
- Client detail + meetings list (useClient, useClientMeetings): status badges
  (CREATED/PROCESSING/COMPLETED/FAILED); useClientMeetings polls every 2s while any
  meeting is CREATED/PROCESSING, stops otherwise.
- Search page (RAG): useSearch useMutation -> POST /api/v1/search; answer + sources
  with scores. (Tenant-wide by design; backend SearchRequest.client_id is optional and
  not yet sent from the UI.)

Frontend (2026-10-12 session) — mentor mode continued:
- **Create-meeting form DONE** (closes the end-to-end async loop from the UI):
  MeetingCreate type (mirrors backend schema: client_id/title/occurred_at/transcript),
  useCreateMeeting(clientId) hook (POST /api/v1/meetings, invalidates ["meetings", clientId]),
  CreateMeetingForm component (title input + transcript textarea, occurred_at = now ISO,
  clears fields on success), wired into ClientDetail above the meetings list. Verified live:
  create -> CREATED -> worker -> PROCESSING -> COMPLETED visible via polling.
- **Frontend tests DONE** (first suite): Vitest (jsdom) + React Testing Library + jest-dom;
  test/test:watch/test:coverage scripts; shared QueryClient wrapper (retries off). Covers
  api/client (auth header, body serialize, success + error-detail parse), auth/token,
  useCreateMeeting (payload + scoped invalidation + error), CreateMeetingForm (user submit
  flow, ISO timestamp, field clearing, error display). 14 tests passing. **PUSHED to
  origin/main** (b37cddb feat create-meeting, 41afe38 test setup+suite).
Known issues (flagged, not fixed): backend container stalls on boot because `uv run`
re-syncs dev deps at runtime (image built --no-dev) — recovered via restart; clean fix is
to call .venv/bin/uvicorn directly in the Dockerfile CMD. Mock embedding provider makes all
search scores ~1.000 (not a bug). Latent runaway-poll risk if a meeting never reaches a
terminal state (worker down).

Next frontend steps (optional): client-scoped search (send client_id), create-client /
create-meeting empty-submit guards, more component coverage. Then Phases 8-9.

Next backend phase: Phase 8 (Kubernetes) — Helm charts, deployments per service, HPA.
(Phases 1-7 complete.)

## Phase 7 log (2026-10-11)

- **Structured logging** (`app/core/logging.py`): JSON logs to stdout; a `correlation_id`
  context var is injected into every record. `configure_logging()` installs it (API +
  workers).
- **Correlation id across services** (SPEC §30 / §31 Q29): `ObservabilityMiddleware` reads
  `X-Request-ID` (or generates one), binds it, and echoes it back. The id is carried in the
  MeetingCreated outbox payload → the AI worker binds it → one meeting is traceable end to
  end across API + workers via a shared id (correlation-id "tracing"; full OpenTelemetry is a
  future upgrade).
- **Metrics** (`app/core/metrics.py` + `/metrics`): Prometheus RED metrics (request count +
  latency histogram), labeled by method/route-template/status (bounded cardinality).
- Access logging: one structured line per request (method, path, status, duration, cid).
- Dep: `prometheus-client`. 62 backend tests passing (+5 observability).

## Phase 6 log (2026-10-11)

- MCP server (`app/mcp/`): HTTP/SSE transport (FastMCP), per-request bearer-JWT auth
  (public-key verify, ADR-009); the server is an application boundary (never touches the
  DB directly — ADR-006 / SYSTEMDESING §19).
- 4 read-only tools (SYSTEMDESING §19): `search_client_history` (reuses RetrievalService /
  RAG), `get_client_context`, `get_recent_meetings`, `get_open_action_items`. All go through
  the service/repo layer, tenant-scoped from the token (never a tool arg).
- Audit: `mcp_audit_logs` table + migration; every call (success/error/unauthorized) writes
  a durable row; auth failures leak no tenant. Shared `_run_tool` runner centralizes
  auth → work → audit.
- ADR-006 (mcp-application-boundary) written. Pinned `mcp>=1.2,<2` (stable FastMCP line).
- Architecture doc: `docs/architecture/07-mcp-rag-flow.md`. 57 backend tests passing.

## Phase 5 log (2026-09-28)

- Mock CRM (`app/mock_crm/`): standalone simulated external system in its own container.
  Idempotent `POST /crm/action-items` keyed by `Idempotency-Key`; failure/latency
  injection (`MOCK_CRM_FAILURE_RATE`/`MOCK_CRM_LATENCY_MS`, `X-Mock-Fail` header) to
  exercise the worker's retry path. Commit `370eec0`.
- CRM client (`app/integrations/crm/`): `CRMClient` protocol mirroring `LLMProvider`;
  transient (`CRMUnavailable`) vs permanent (`CRMBadRequest`) error taxonomy. `HTTPCRMClient`
  retries transient failures with exponential backoff + jitter, never retries 4xx, sends a
  stable idempotency key across retries. Commit `370eec0`.
- CRM sync worker (`app/workers/crm_worker.py`): 3rd consumer of IntelligenceExtracted
  (group `crm_worker`, own idempotency marker). Reasoned in a mentor session; control flow:
  permanent 4xx -> DLQ (`crm.sync.dlq`) + mark processed; transient 5xx -> propagate ->
  circuit breaker trips -> PAUSE consumption (Kafka buffers the backlog) -> half-open probe
  on cool-down -> resume. Upholds "eventual sync" (failure scenario F).
- Circuit breaker (`app/workers/circuit_breaker.py`): closed/open/half-open, injectable clock.
- Verified live e2e: meeting -> AI extract -> IntelligenceExtracted -> crm-worker -> mock CRM;
  action item landed with correct client_ref, no DLQ messages. 46 tests passing (11 new).
- Dockerfile now copies alembic + scripts so migrations/seed run in-container (was host-only).

---

## Definition of Done (SPEC §50)

- [x] React frontend runs locally
- [x] Python backend runs locally
- [x] MySQL runs through Docker
- [x] users can authenticate
- [x] tenants are isolated
- [x] clients can be created
- [x] meetings can be created
- [x] meetings are processed asynchronously
- [x] Kafka is used for processing events
- [x] AI analysis produces structured output
- [x] LLM output is validated
- [x] client intelligence is persisted
- [x] historical semantic search works
- [x] basic RAG works
- [x] mock CRM integration works
- [x] CRM failures are retried
- [x] consumers are idempotent
- [x] MCP server exposes read-only tools
- [x] MCP respects authorization
- [x] MCP requests are audited
- [x] frontend displays processing status
- [x] logs are structured
- [x] metrics exist
- [x] unit tests exist
- [x] integration tests exist
- [x] Docker Compose starts the application
- [ ] Helm deployment exists
- [ ] Terraform architecture exists
- [ ] CI pipeline runs tests and builds images
- [ ] README explains architecture and tradeoffs

---

## Phase checklist (SPEC §43)

- [x] Phase 1 — Foundation (React → FastAPI → MySQL; auth, clients, meetings)
- [x] Phase 2 — AI Processing (LLM abstraction, mock, structured extraction, validation)
- [x] Phase 3 — Kafka (events, AI worker, idempotency, retries)
- [x] Phase 4 — Search/RAG (chunking, embeddings, vector search, retrieval)
- [x] Phase 5 — CRM (mock CRM, worker, retries, DLQ, idempotency)
- [x] Phase 6 — MCP (read-only tools, auth, audit)
- [x] Phase 7 — Production engineering (logging, metrics, tracing, health)
- [ ] Phase 8 — Kubernetes (Helm, deployments, HPA)
- [ ] Phase 9 — Terraform/AWS

---

## Last session summary (2026-09-22)

- Analyzed `SPEC.md`; established scope.
- Locked three decisions: vector store (MySQL + separate pgvector), LLM provider
  (Anthropic; Mock default), backend tooling (uv). ADRs recorded in `docs/decisions/`.
- Chose **monorepo** (rationale captured in `docs/decisions/0004-monorepo.md`).
- Created `clientlens/` repo with personal git identity
  (Levente Csanyi <csanyi.levente@lunkwill.hu>), SSH origin
  `git@github.com:csanyilevente8/clientlens.git`, branch `main`.
- Built the SPEC §51 directory structure; added `.gitignore`, README, this file, ADRs.
- Not yet pushed to remote (awaiting go-ahead).
- Disabled commit + push signing repo-locally (default signing used a different key
  identity than intended for this project); recreated the commit unsigned as `585ce35`.
  Repo uses the personal identity below. Global git config untouched.
- **Pushed to `origin main` successfully.** Session ended here.
- NOTE: doc edits made after the push (this update + WORKSPACE.md) are uncommitted —
  commit them at the start of next session before Phase 1 work.

## Next steps

1. Auth (JWT) → clients → meetings CRUD with tenant isolation (SPEC §8, §9, §26).
   First domain models (Tenant, User, Client) + first Alembic migration.
2. Frontend Vite skeleton calling `/health`, then app pages.
   Follow SPEC §52 rhythm at each step.

## Phase 1 log

- 2026-09-23: backend foundation. `uv` (0.12.18), Python pinned 3.12, `pyproject.toml`
  (FastAPI/uvicorn/pydantic-settings + dev pytest/httpx/ruff). App factory, Pydantic
  settings, `/health`. Test passes; ruff clean; uvicorn boots; OpenAPI generated.
- 2026-09-23: MySQL wiring. Added SQLAlchemy async + asyncmy + cryptography (needed for
  MySQL 8 caching_sha2_password) + Alembic (async env.py targeting Base.metadata).
  `core/db.py` (engine/session/Base/get_session dependency). `/ready` readiness endpoint
  (DB ping) separate from `/health` liveness. `docker-compose.yml` (MySQL 8 + backend),
  backend `Dockerfile` (uv). Verified end-to-end: `docker compose up` → `/ready` returns
  200 `{"status":"ready","database":"ok"}`. No Alembic migrations yet (no models).

## Open questions / pending

- None blocking. (Multi-repo split deferred; monorepo confirmed.)
