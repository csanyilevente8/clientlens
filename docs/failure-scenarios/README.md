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
