# ADR-004 — MySQL as source of truth; separate vector store for semantic search

Status: Accepted (2026-09-22, reformatted 2026-09-23 to the SYSTEMDESING §27 template)

## Decision

Use **MySQL 8** as the single transactional source of truth. Use a **separate
PostgreSQL + pgvector** service for semantic (vector) search. Both sit behind repository
abstractions.

## Context

ClientLens stores structured, relational data (tenants, users, clients, meetings, goals,
action items) and also needs semantic retrieval over meeting transcripts ("find where the
client worried about retirement"). These are two different retrieval models (SYSTEMDESING
§18): exact/relational filtering vs. approximate nearest-neighbour over embeddings.

## Requirements

- Strong consistency for transactional writes (create client, save meeting metadata) —
  SYSTEMDESING §17.
- Semantic similarity search over transcript chunks (eventual consistency acceptable).
- Tenant isolation enforceable at the query layer.
- Ability to explain why relational and vector data are separated.

## Options

1. **MySQL only**, store embeddings as BLOB/JSON and compute similarity in-app — no ANN
   index, O(n) scans, does not scale.
2. **Postgres + pgvector for everything** (drop MySQL) — one DB, but contradicts the
   mandated MySQL requirement and collapses the transactional-vs-semantic distinction the
   project is meant to teach.
3. **MySQL primary + dedicated vector DB (Qdrant/Weaviate)** — production-realistic but
   adds a new technology with little extra pedagogical value here.
4. **MySQL primary + separate Postgres/pgvector** (chosen).

## Why

Option 4 keeps MySQL as the authoritative relational store while giving a real ANN index
for semantic search, and makes the "two retrieval models" boundary explicit. pgvector is
enough to learn the concepts without a new vendor.

## Trade-offs

- Extra container/service to run and operate.
- Two datastores to keep consistent (embeddings are derived, eventually consistent from
  the meeting text — acceptable per §17).
- Cross-store queries assembled in the application/retrieval layer, not the DB.

## Failure modes

- **Vector DB down:** core relational features (clients, meetings, structured reads) keep
  working; only semantic search/RAG degrades (SYSTEMDESING §21 matrix).
- **MySQL down:** API fails safely; writes rejected rather than silently lost.
- **Embedding drift / re-index needed:** since MySQL is source of truth, the vector store
  can be rebuilt from transcripts.

## Consequences

- Repository abstractions must exist early so the vector backend can be swapped.
- Indexing is an asynchronous, eventually-consistent step (feeds the Kafka/worker design).

## When we would reconsider this decision

- If operational cost of two datastores outweighs the benefit at our scale.
- If MySQL gains a production-grade vector index we trust, collapsing to one store.
- If semantic search volume demands a dedicated, horizontally-scaled vector DB (Exercise B,
  100x traffic).
