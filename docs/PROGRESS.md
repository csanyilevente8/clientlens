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
Next: Phase 3 — Kafka + async (202 + outbox + worker + idempotency + retries/DLQ).

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
- [ ] mock CRM integration works
- [ ] CRM failures are retried
- [ ] consumers are idempotent
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
- [ ] Phase 5 — CRM (mock CRM, worker, retries, DLQ, idempotency)
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
