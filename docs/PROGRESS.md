# ClientLens — Progress

Detailed, versioned progress for this repo. The workspace-level entry point is
`../WORKSPACE.md` (one level up, outside git). Read that first, then this.

---

## Current phase

**Pre-Phase 1** — scaffolding complete, no application code yet.

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

## Next steps

1. First commit; push to `origin main` when approved.
2. Begin **Phase 1**: backend `pyproject.toml` (uv) + FastAPI skeleton, health endpoint,
   MySQL via docker-compose, then auth → clients → meetings. Frontend Vite skeleton.
   Tests at each step. Goal: React → FastAPI → MySQL.

## Open questions / pending

- None blocking. (Multi-repo split deferred; monorepo confirmed.)
