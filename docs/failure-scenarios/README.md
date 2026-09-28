# Failure Scenarios

The failure matrix (SYSTEMDESING §21) and the failure-injection exercises (§28 A–F).

## Failure matrix (target behavior)

| Component | Failure     | Expected behavior           |
| --------- | ----------- | --------------------------- |
| MySQL     | unavailable | API fails safely            |
| Kafka     | unavailable | outbox accumulates          |
| LLM       | unavailable | job retries                 |
| Vector DB | unavailable | core DB remains available   |
| CRM       | unavailable | CRM sync remains pending    |
| AI worker | crashes     | Kafka redelivers            |
| MCP       | unavailable | LLM cannot retrieve context |

## Exercises (to run once the async pipeline exists)

- A — 10x traffic
- B — 100x traffic
- C — LLM outage (30 min)
- D — Worker crash mid-processing
- E — Kafka unavailable (outbox consistency)
- F — CRM unavailable (PENDING → retry → eventual sync)

Each exercise: what we did, what we observed, what it proves.

---

## Synchronous vs asynchronous processing — failure comparison

Reasoned during the Stage-2 bottleneck analysis (see `../capacity/`). These are the
failure modes of the *current* synchronous meeting processing, and how async fixes each.

### Scenario: LLM is down for 30 minutes

**Synchronous (current):** create-meeting calls the LLM inline. With the commit at the end
of the request, an LLM failure propagates as a 5xx and can **roll back the whole request —
losing the meeting the advisor just typed.** Ingestion and processing are welded together,
so a *processing* failure becomes an *ingestion* failure.

**Async:** persist the meeting durably (CREATED) and enqueue an event *before* any LLM call,
then return 202. If the LLM is down, meetings keep being accepted; events wait in the queue
(and/or retry). When the LLM recovers, workers drain the backlog. **Nothing is lost** — only
processing is delayed.

**Principle:** commit ingestion durably *before* attempting slow/fallible work.

### Scenario: process crashes mid-processing (OOM / deploy / kill -9)

**Synchronous (current):** meeting saved as CREATED, processing starts, process crashes at
second 10. No `except`/cleanup runs, so the meeting is stuck in **PROCESSING forever** — an
orphaned "zombie" record. **Nothing retries it** (no record that work was owed — that fact
lived only in the crashed process's memory), and **nobody notices** without a separate
sweeper guessing at "stuck too long."

**Async:** the "work is owed" fact lives **durably in the queue**, not in process memory.
The worker only **acks** after success; a crash before ack means the queue **redelivers**
the event to another worker. The meeting gets processed. **Nothing is lost.**

### The queue property that guarantees survival

Queues provide **at-least-once** delivery (configurable): an event stays in the queue until
the consumer **acknowledges** success; no ack → **redelivery**. This is what makes async
survive worker crashes and dependency outages.

**Trade-off it introduces:** at-least-once means the **same event can be delivered twice**
(e.g. worker saves the result, then crashes before acking → redelivered → processed again).
Therefore consumers must be **idempotent** (processed_events table / transactional outbox,
SYSTEMDESING §10/§13). Addressed in Phase 3.

---

## Executed failure exercises (Phase 3, live stack)

Run against the full docker-compose stack (mysql, kafka KRaft, backend, publisher,
ai-worker). Verified 2026-09-28.

### Exercise E — Kafka unavailable (§28 E)

Steps: `docker compose stop kafka` → create a meeting via the API → restart kafka.

Observed:
- Create returned **202 + status CREATED** *while Kafka was down* — ingestion is unaffected
  by the broker outage (the meeting + outbox row commit to MySQL, no Kafka on the request
  path).
- Meeting stayed **CREATED** during the outage (event sat unpublished in the outbox / could
  not be consumed).
- After `docker compose start kafka`, the publisher drained the outbox and the worker
  processed it → **COMPLETED** within ~15-20s (Kafka warmup + reconnect).

Proves: **the transactional outbox means no event is lost across a broker outage**; the
system self-heals when Kafka returns. Matches the failure-matrix row "Kafka unavailable →
outbox accumulates".

### Exercise D — worker crash / down (§28 D)

Steps: `docker compose kill ai-worker` → create a meeting → restart the worker.

Observed:
- With no worker consuming, the meeting stayed **CREATED** (the event was published to Kafka
  and retained there).
- After `docker compose up -d ai-worker`, the worker consumed the buffered event
  (`auto_offset_reset=earliest`, offset never committed) → **COMPLETED**.

Proves: **a worker being down/crashing does not lose work** — Kafka retains the event until a
worker successfully processes it and commits its offset. Combined with the idempotency guard
(processed_events + UNIQUE), a crash *mid-processing* redelivers and reprocesses without
duplicates. Matches "AI worker crashes → Kafka redelivers".

### Known dev-only simplifications observed

- JWT keys are generated per-container in the image (gitignored → absent from a clean
  build). Fine for a single API replica; multiple replicas would need shared/injected keys
  (prod: secrets, per ADR-009).
- `uv run` entrypoints re-sync on container start (slow cold start); a prod image would use
  the venv directly.
