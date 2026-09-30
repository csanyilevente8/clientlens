# Event-Driven vs Direct-Call — the Meeting Pipeline (SYSTEMDESING §7, §14, §34-35)

Why the meeting pipeline is **event-driven** (outbox → Kafka → three consumers) instead of
**direct synchronous calls**, what that choice bought, and what it cost. This is the
"reasoning, not memorized answers" write-up (SYSTEMDESING §34) for the async decision.

Related: `capacity/bottleneck-synchronous-processing.md` (the latency/throughput argument),
`failure-scenarios/` (what breaks), `adr/ADR-004` (source of truth). This doc is the
*architectural style* argument that sits on top of those.

---

## Two orthogonal questions (don't conflate them)

- **Microservices** = *how you decompose/deploy* (structure): independently deployable
  units, each owning a slice + its data.
- **Event-driven** = *how components communicate* (interaction): react to facts that
  happened, rather than calling each other directly.

They're independent axes. ClientLens is **both**: separately-deployable services (api,
publisher, ai-worker, index-worker, crm-worker, mock-crm) that communicate via **events**
at the core — but still use **direct request/response** where an immediate answer is
needed (login, create client, RAG query). The style is chosen *per interaction*, not once
globally.

---

## What the code actually does (event-driven)

`POST /meetings` (see `app/api/meetings.py`):

```
POST /meetings
  ├─ INSERT meeting  ┐
  ├─ INSERT outbox   ┘  ONE transaction  (atomic write + event)
  └─ return 202 Accepted            ◄── caller done in ~milliseconds

... decoupled in time ...

publisher (separate process, polls outbox ~1s)  → Kafka "meeting.created"
        ↓
   ai-worker  (consumes meeting.created)
     ├─ LLM analysis  (the slow part — seconds)
     ├─ persist intelligence + INSERT outbox(IntelligenceExtracted)  ← atomic
     └─ commit
        ↓  publisher drains → "intelligence.extracted"
        ├──► index-worker  (chunk → embed → pgvector)     ┐ two independent
        └──► crm-worker    (push action items → mock CRM) ┘ consumers, in parallel
```

Two properties that define the style, both visible in the code:
- The API **names none** of the LLM, vector store, or CRM. It writes one row + one outbox
  event and returns. Producers don't know their consumers.
- `IntelligenceExtracted` has **three** independent consumers; the producer (ai-worker)
  knows about **zero** of them. Adding a fourth = add a consumer, change nothing upstream.

## The direct-call version (this was literally Stage 1)

`app/api/meetings.py` still documents it: *"processing is SYNCHRONOUS here on purpose …
we will later replace with async."*

```
POST /meetings
  ├─ INSERT meeting
  ├─ LLM.analyze(transcript)      ← blocks, seconds
  ├─ INSERT intelligence
  ├─ VectorStore.index(chunks)    ← blocks
  ├─ CRM.sync(action_items)       ← blocks, external network
  └─ return 200 OK                ◄── caller waited for ALL of it
```

---

## Side-by-side: bought vs cost

| Dimension | Direct-call | Event-driven (today) |
|---|---|---|
| API latency | seconds (waits on LLM+index+CRM) | milliseconds (write + 202) |
| Coupling | API imports/calls LLM, vector, CRM | API knows none of them |
| Add a reaction | edit endpoint, redeploy API | add a consumer; API untouched |
| CRM down | **meeting creation fails** | meeting fine; crm-worker breaker holds backlog, syncs on recovery |
| Scaling slow work | can't — LLM scales with API replicas | ai-worker scales independently (§14: api×3, ai×10, crm×2) |
| Consistency | strong — 200 = all done | eventual — 202 = accepted; status field tracks progress |
| Failure mode | loud, immediate (error in response) | quiet, deferred (event waits in log; needs status/DLQ/logs) |
| Debuggability | one stack trace | spread across workers; need event_id correlation |
| Extra machinery | none | outbox, processed_events, retries, DLQ, circuit breaker |

## What it bought

- **Failure isolation** — a slow LLM or a down CRM no longer breaks meeting creation. The
  request path touches only MySQL.
- **Independent scaling** — the expensive work (LLM) scales on queue backlog, separately
  from API request traffic (different resource profiles; SYSTEMDESING §14).
- **Loose coupling / extensibility** — fan-out to N consumers with zero upstream change.

## What it cost

- **Eventual consistency** — "done" became "accepted; check status later."
- **New reliability machinery**, each solving a problem async *created*:
  - outbox (atomic business-write + event; no lost/ghost events),
  - `processed_events` idempotency (at-least-once delivery ⇒ duplicates; see the
    publisher's "crash between publish and mark published_at" comment),
  - retries + DLQ (transient vs poison),
  - circuit breaker (a sustained CRM outage shouldn't melt the pipeline).
- **Harder debugging** — one logical request now spans 3 processes.

---

## The decision rule (the actual interview answer)

Go async **only where** the work is (a) slow, (b) depends on flaky externals, or (c) fans
out to multiple independent reactions. The meeting pipeline is all three (slow LLM, flaky
CRM, fan-out to index+CRM) — that's what justifies the machinery. A single fast synchronous
consumer would **not** have justified Kafka + outbox + DLQ.

Everything that needs an immediate, consistent answer stayed **synchronous REST**: login,
create client, the RAG query. We did not "go event-driven" globally; we moved *exactly the
bottleneck and the fan-out* off the request path.

## Interview soundbites

- "Microservices is a **structure** decision; event-driven is a **communication**
  decision. We're both, but we chose the communication style per interaction."
- "The producer of `IntelligenceExtracted` knows **zero** of its three consumers — that
  decoupling is the whole point, and the cost is eventual consistency + idempotency."
- "Kafka here is justified by **fan-out + slow/flaky downstreams**, not by 'microservices.'
  One fast consumer wouldn't have earned the outbox/DLQ complexity."
- "Async didn't remove work — it **moved** it: from request latency to operational
  machinery (outbox, idempotency, DLQ, breaker)."
