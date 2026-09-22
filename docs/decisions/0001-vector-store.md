# ADR 0001 — Vector store: MySQL primary + separate PostgreSQL/pgvector

Status: Accepted (2026-09-22)

## Context

The spec mandates MySQL 8 as the primary transactional database (§7) but wants semantic
search over meeting content (§18), suggesting "PostgreSQL + pgvector if practical" and
leaving the vector store's placement open. A core learning objective is understanding why
transactional and semantic/vector data are separated (§7 item 7, §18).

## Decision

- **MySQL 8** remains the single source of truth for transactional data.
- Semantic search uses a **separate PostgreSQL + pgvector** service, running as its own
  container.
- Both stores sit behind repository abstractions so application/business code does not
  depend on where data lives.

## Alternatives considered

- **Qdrant / dedicated vector DB** — production-realistic, but adds a new technology to
  learn without extra pedagogical value over pgvector for this project.
- **Postgres + pgvector for everything (drop MySQL)** — simplest local setup, but
  contradicts the mandated MySQL requirement and eliminates the transactional-vs-semantic
  separation the project is meant to demonstrate.

## Consequences

- One extra container in local dev and Kubernetes.
- Clear, defensible answer for Interview Exercise 6 (scaling retrieval to 100M chunks).
- Repository abstractions must be defined early so swapping the vector backend stays cheap.
