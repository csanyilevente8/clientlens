# Bottleneck Analysis — Synchronous Meeting Processing (SYSTEMDESING §5 Stage 2)

We built meeting processing **synchronously on purpose** (Stage 1): the create-meeting
request runs the "analysis" inline and blocks until it finishes. This document is the
Stage-2 analysis of *why that is wrong*, which justifies moving to asynchronous processing
(Phase 3) — rather than adding that complexity blindly.

## The setup

- `POST /meetings` persists the meeting, then calls processing **inline** and only returns
  when it completes. Current stand-in delay is ~2s; real LLM analysis can be **20s+**.
- Peak load (see capacity doc): **~10 meetings/second**.

## The concurrency math (Little's Law)

```
concurrent in-flight = arrival_rate × time_in_system
                     = 10 meetings/s × 20 s
                     = 200 meetings being processed simultaneously
```

At peak, ~**200 requests** are in flight at once, each holding a worker/connection **for 20
seconds** — doing nothing but waiting on the LLM over the network.

## What actually breaks: worker-pool exhaustion (not CPU)

A web server has a limited **worker/connection pool** (tens to low hundreds). Say 50 slots.
We need 200 concurrent but have 50:

- Meetings #1-50 grab every worker and park for 20s each.
- Meeting #51+ has **no free worker** → queues, times out, or is rejected.
- Critically, those 50 workers use **almost no CPU** — they are **blocked waiting** on a
  network call. The server looks 100% "busy" (no free workers) while being nearly idle
  (no real work). This is **concurrency exhaustion, not compute exhaustion.**

### Blast radius: the whole API goes down

Because meeting processing hogs every worker slot, **unrelated endpoints (login, list
clients, health) cannot get a worker either.** One slow endpoint takes down the entire API.

## Why "just add API instances" is the wrong first answer

Scaling the whole API to absorb 200 blocked-waiting requests means paying for a large fleet
of expensive general-purpose servers that mostly **sleep on network calls**. It also
couples fast endpoints (login) to slow ones (processing), forcing them to scale together
despite completely different resource profiles.

The real problem is not a shortage of servers — it is that **slow, blocking work is on the
request path at all.**

## The fix: get slow work off the request path (async)

```
POST /meetings
  → persist meeting (CREATED) + enqueue an event   [milliseconds]
  → return 202 Accepted immediately                (worker freed instantly)
        ↓
  separate worker pool consumes the queue → does the 20s LLM processing
        ↓
  updates status → COMPLETED
```

- The API worker is held for **milliseconds**, not 20 seconds → worker-pool exhaustion
  disappears.
- **Workers scale independently** from the API. If the queue backs up, add *workers*
  (cheap, purpose-built for slow processing) — not API servers. Different workloads,
  different scaling dimensions (SYSTEMDESING §14).

## Interview soundbites

- "The bottleneck is the **worker/connection pool held by blocked waiters**, not CPU."
- "Size for **peak (~10/s)**, not average (0.63/s)."
- "Little's Law: 10/s × 20s = **200 concurrent** → exhausts a 50-slot pool → whole API
  unresponsive, including login."
- "Fix isn't more API servers — it's moving slow work off the request path; return **202**
  and process in independently-scaled workers."

## Consequence that seeds Phase 3

Async introduces a queue with **at-least-once** delivery (survives worker crashes via
redelivery — see failure-scenarios). At-least-once means the **same event can be delivered
twice** → consumers must be **idempotent** (processed_events table / outbox, §13/§10).
The reliability we gain *creates* the duplicate problem Phase 3 solves.
