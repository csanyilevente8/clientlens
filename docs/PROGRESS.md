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
Frontend commits NOT yet counted in the push tally below until pushed this session.
Next frontend steps: create-client form (useMutation + cache invalidation), client detail
+ meetings (status display), search page (RAG). Then optionally Phases 5-9.

Next backend phase: Phase 6 (MCP) — read-only tools, auth, audit (reuses the
RetrievalService built in Phase 4).

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

- [ ] React frontend runs locally
- [ ] Python backend runs locally
- [ ] MySQL runs through Docker
- [ ] users can authenticate
- [ ] tenants are isolated
- [ ] clients can be created
- [ ] meetings can be created
- [ ] meetings are processed asynchronously
- [ ] Kafka is used for processing events
- [ ] AI analysis produces structured output
- [ ] LLM output is validated
- [ ] client intelligence is persisted
- [ ] historical semantic search works
- [ ] basic RAG works
- [x] mock CRM integration works
- [x] CRM failures are retried
- [x] consumers are idempotent
- [ ] MCP server exposes read-only tools
- [ ] MCP respects authorization
- [ ] MCP requests are audited
- [ ] frontend displays processing status
- [ ] logs are structured
- [ ] metrics exist
- [ ] unit tests exist
- [ ] integration tests exist
- [ ] Docker Compose starts the application
- [ ] Helm deployment exists
- [ ] Terraform architecture exists
- [ ] CI pipeline runs tests and builds images
- [ ] README explains architecture and tradeoffs

---

## Phase checklist (SPEC §43)

- [ ] Phase 1 — Foundation (React → FastAPI → MySQL; auth, clients, meetings)
- [ ] Phase 2 — AI Processing (LLM abstraction, mock, structured extraction, validation)
- [ ] Phase 3 — Kafka (events, AI worker, idempotency, retries)
- [ ] Phase 4 — Search/RAG (chunking, embeddings, vector search, retrieval)
- [x] Phase 5 — CRM (mock CRM, worker, retries, DLQ, idempotency)
- [ ] Phase 6 — MCP (read-only tools, auth, audit)
- [ ] Phase 7 — Production engineering (logging, metrics, tracing, health)
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
