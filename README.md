# ClientLens

An AI-powered client intelligence platform for financial advisors.

> **Educational project.** The goal is production-style engineering and being able to
> explain architectural tradeoffs — not feature count. See `../SPEC.md` (workspace root)
> for full requirements and `docs/` for architecture, decisions, and progress.

## What it does

Advisors upload meeting transcripts; an LLM extracts structured client intelligence
(topics, goals, concerns, action items, life events); it is persisted with provenance,
synced to a mock CRM, made semantically searchable, and exposed read-only to an external
reasoning model (Claude) via an MCP server.

## Architecture (high level)

```
React/TS → FastAPI → { MySQL (transactional), Kafka (events) }
                            │
              ┌─────────────┼──────────────┐
           AI Worker      Indexer       CRM Worker
              │             │               │
          Anthropic    pgvector        Mock CRM
              ▼
   Client Intelligence → Retrieval Service → MCP Server → Claude
```

## Key decisions

- **MySQL 8** for transactional data + **separate PostgreSQL/pgvector** for semantic search
  (see `docs/decisions/0001-vector-store.md`).
- **Anthropic (Claude)** as the real LLM provider; **Mock** default for dev/test
  (see `docs/decisions/0002-llm-provider.md`).
- **uv** for Python tooling (see `docs/decisions/0003-backend-tooling.md`).
- **Monorepo**, multiple independently deployable services.

## Status

Pre-Phase 1 (scaffolding). See `docs/PROGRESS.md`.

## Getting started

_Not yet available — Phase 1 will add `docker compose up` for local development._
