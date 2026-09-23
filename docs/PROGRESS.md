# ClientLens — Progress

Detailed, versioned progress for this repo. The workspace-level entry point is
`../WORKSPACE.md` (one level up, outside git). Read that first, then this.

---

## Current phase

**Phase 1 (Foundation) — in progress.**
Done: backend skeleton (FastAPI app factory, Pydantic settings, `/health`), uv + Python
3.12 pinned, pytest passing, ruff clean. MySQL 8 wired via docker-compose; SQLAlchemy
(async) + Alembic set up; `/ready` readiness endpoint pings the DB and returns 200 with
the stack up. `docker compose up` starts MySQL + backend.
Next in Phase 1: auth (JWT) → clients → meetings CRUD with tenant isolation, then frontend.

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
