# Senior Interview — Full Explanations & Examples

Consolidated from mentoring conversation (2026-09-29). Covers the 8 interview topics with
definitions, examples, ClientLens references, Java→Python bridges **[bridge]**, likely
follow-ups, and interview soundbites. Companion to `theory-topics.md` (which has the
condensed cheat-sheet + weak-spot drills).

Topics: SOLID/OOP · REST API · Idempotency · Concurrency & Multithreading ·
Python + Deadlock · SQL · Testing · Frontend (React, TypeScript)

Delivery rule for every answer: **definition → why/tradeoff → concrete example (ClientLens)
→ failure mode.** Volunteer the tradeoff and failure mode unprompted.

---

# 1. SOLID / OOP

## Core OOP
- **Encapsulation** — hide internal state; expose behavior. Keeps invariants valid.
- **Abstraction** — expose *what*, hide *how* (interface vs implementation).
- **Inheritance** — reuse via is-a. **Prefer composition over inheritance** (inheritance
  couples tightly; composition is flexible). Say this unprompted.
- **Polymorphism** — same interface, many implementations, chosen at runtime.

## SOLID
- **S — Single Responsibility:** one reason to change.
- **O — Open/Closed:** open to extension, closed to modification (add cases without editing
  callers).
- **L — Liskov Substitution:** a subtype must work anywhere the base does — no strengthened
  preconditions, no weakened postconditions, no surprises. *Violation example:* `Square
  extends Rectangle` where `setWidth` also changes height, breaking callers who assume
  independent dimensions.
- **I — Interface Segregation:** many small focused interfaces beat one fat one; don't force
  clients to depend on methods they don't use.
- **D — Dependency Inversion:** high-level and low-level modules both depend on
  **abstractions**, not each other; details depend on abstractions. The key word is
  **direction** of dependency, not size. Normally high-level calls down into low-level (and
  depends on it); DIP **inverts** that by inserting an interface the high-level module owns
  and the low-level detail conforms to.

## DIP vs DI (name the distinction — senior signal)
- **DIP** = the principle ("depend on abstractions").
- **DI (dependency injection)** = the technique that supplies the concrete implementation
  (constructor injection, FastAPI `Depends`, Spring `@Autowired`).
- DI ≠ service locator: DI pushes deps in (explicit, testable); a service locator pulls them
  (hidden deps, harder to test).

## Concrete gains of DIP (have three ready — not just "flexibility")
1. **Testability** — inject a fake/in-memory implementation in tests (most compelling).
2. **Swappability** — change Postgres → MySQL without touching business logic.
3. **Decoupling** — teams code against the interface independently.

## How ClientLens does it
- **S:** workers split the pure core (`handle_meeting_created`) from the Kafka loop
  (`run_ai_worker`) — processing vs transport; also why the core is unit-testable.
- **O:** `get_llm_provider()` factory — adding Anthropic = new class + one branch, no
  business-logic change. Same for `CRMClient`, `EmbeddingProvider`.
- **L:** any `LLMProvider` (Mock / real) is interchangeable; Mock honors the same contract.
- **I:** small `Protocol`s — `LLMProvider`, `CRMClient`, `EventBus`, `EmbeddingProvider`.
- **D:** business code depends on the `CRMClient` protocol, never on httpx; `HTTPCRMClient`
  is injected.
- **Best example:** `TenantScopedRepository[ModelT: Base]` — generic base + 2-line
  subclasses (`ClientRepository(TenantScopedRepository[Client])`). Encapsulates the tenant
  filter so callers *can't* forget it — "the safe path is the default path."

## [bridge]
Java `interface` = Python `Protocol` (structural/duck typing — conform by shape, no
`implements`). Spring `@Autowired` DI = constructor injection / FastAPI `Depends`.

## Likely follow-ups
- "Inheritance vs composition?" → composition = looser coupling; inheritance for true is-a
  only (overuse → fragile base class).
- "Give an LSP violation." → the Square/Rectangle case.
- "DI vs service locator?" → push vs pull; DI is testable/explicit.

---

# 2. REST API

## Know
- **Verbs:** GET (read, safe), POST (create/action), PUT (replace), PATCH (partial), DELETE.
- **Status codes:** 200 OK · 201 Created · **202 Accepted (async)** · 204 No Content ·
  400 bad request · 401 unauthenticated · 403 unauthorized · 404 not found · 409 conflict ·
  422 validation · 429 rate limit · 500 server · 503 unavailable.
- **Statelessness:** no server session; each request self-contained (JWT) → any replica
  serves any request → horizontal scaling.
- **Method idempotency (per spec):** GET/HEAD safe; GET/PUT/DELETE idempotent; **POST is
  NOT** → needs idempotency keys for safe retries.
- **Versioning:** URL (`/api/v1`, explicit, cache-friendly) vs header/content-negotiation
  (clean URLs). Tradeoff = explicitness vs URL purity.

## 202 Accepted — the deep answer (common interview question)
`POST /meetings` returns **202, not 201**, because processing is **async**: the server
durably accepted the request and enqueues the work; the result comes later.
- **Why design it this way:** inline (sync) processing means long response times, and worse,
  a downstream outage would fail the whole request instead of letting us retry later.
- **What the client must do differently:** with 201 the resource is *done* and returned;
  with 202 the client **cannot assume the result exists** — creation and completion are two
  separate moments. It must:
  1. **Poll a status endpoint** — `GET /meetings/{id}`, watch `status`: CREATED → PROCESSING
     → COMPLETED / FAILED. (ClientLens has a `status` column for exactly this; the frontend
     polls with `refetchInterval` while pending.)
  2. **Or be notified** — webhook / WebSocket / server-sent events.
- Spec note: a 202 should point the client at where to monitor progress (status URL /
  `Location` header).

## How ClientLens does it
- `POST /clients` → 201. `POST /meetings` → **202** (reflects the event-driven backend).
- `GET /clients/{id}` → 200 or **404 even for another tenant's real id** (don't leak
  existence). `DELETE` → 204. Stateless JWT (RS256; workers/MCP verify with the public key).
  `/api/v1/...` URL versioning.

## Likely follow-ups
- "Is POST idempotent? Make double-submit safe?" → no; idempotency key (Stripe-style; the
  mock CRM's `Idempotency-Key`).
- "200 vs 201 vs 202?" → done+here / created / accepted-not-done-yet.
- "REST vs RPC vs GraphQL?" → resources+verbs+cacheable (over/under-fetch risk) / action-
  oriented / client shapes query, one endpoint, harder caching.
- "Partial failure calling a flaky dependency?" → timeouts, retries+backoff, circuit
  breaker, idempotency keys.

## Soundbite
"Returning 202 instead of 200 tells the client 'I durably accepted this, but the result
comes later' — which is exactly true because the meeting goes through an async pipeline."

---

# 3. Idempotency

## The causal chain (memorize)
> Distributed systems → network failures → must retry → **at-least-once delivery** →
> duplicates → **need idempotency** (make duplicates harmless).

## Definitions
- **Idempotent:** N applications have the same effect as 1.
- **Exactly-once *delivery* is impossible** — the **Two Generals problem**: the sender can't
  tell if the message or the ack was lost, so it must either resend (→ duplicate) or not
  (→ loss). You choose your poison:
  - **at-most-once** (tolerate loss — metrics, fire-and-forget),
  - **at-least-once** (tolerate duplicates — payments, meeting pipeline),
  - exactly-once delivery = myth.
- **Exactly-once *effect*** = at-least-once delivery + idempotent (or transactional)
  consumer. That's what "Kafka exactly-once" really means.
- Idempotency ≠ commutativity (order-independence) ≠ safety (no side effects).
- It's about **effect, not response**: a replay may return a different status (201 then 200)
  but the *state* is unchanged.

## How ClientLens does it
- `processed_events` with **UNIQUE (event_id, consumer_name)**. Two layers:
  - **App-level check** (`_already_processed`) = *optimization* for the common case (avoids
    redoing expensive work like an LLM call).
  - **DB unique constraint** = *correctness guarantee* under the concurrent race (two workers
    both see "not processed," both proceed; the DB serializes the two inserts → one wins,
    the other gets `IntegrityError` and rolls back).
  - One-liner: **"the check is an optimization; the constraint is the guarantee."**
- Marker written **in the same transaction as the work** → "done" and "marked done" can never
  disagree (ACID atomicity). If they were separate commits, a crash between them breaks
  idempotency.
- Keyed **per consumer** because one event has **3 consumers** (AI, index, CRM) — each tracks
  its own processing independently.
- **Cross-store idempotency (advanced):** index worker's marker is in MySQL, chunks in
  pgvector (no shared txn). Solved by making the *work itself* idempotent
  (delete-then-insert) and doing the external write **before** committing the marker → a
  crash between just re-runs the idempotent work on redelivery. Effectively-once without a
  distributed transaction.
- **HTTP layer:** mock CRM dedupes on `Idempotency-Key`; stable key `event_id:item_id` so
  retries never create duplicate CRM tasks.

## The concurrent-duplicate walk-through (a favorite question)
Two copies of the same event hit two workers simultaneously → both attempt to insert the
marker → unique constraint lets one win; the other gets `IntegrityError` → its whole
transaction (result write + marker) rolls back → no duplicate. The winner commits and its
offset advances.

## Likely follow-ups
- "Why not exactly-once delivery?" → Two Generals; you get exactly-once effect.
- "Two workers, same message, same instant?" → the walk-through above.
- "Marker in a different store than the work?" → cross-store idempotency story.
- "How long keep idempotency keys?" → long enough to cover the max retry/redelivery window.

---

# 4. Concurrency & Multithreading

## The definitions (memorize — Rob Pike)
> "Concurrency is about *dealing* with lots of things at once. Parallelism is about *doing*
> lots of things at once."
- **Concurrency** = *dealing with* many things — a **structural** property; tasks interleave
  and make progress over overlapping time. Does NOT require multiple cores.
- **Parallelism** = *doing* many things — **simultaneous** execution; needs multiple cores.
- Concurrency = property of the **design**; parallelism = property of the **hardware**.

### Any combination is possible
|                    | Not parallel (1 core)        | Parallel (many cores)          |
|--------------------|------------------------------|--------------------------------|
| **Not concurrent** | plain single-threaded script | SIMD / pure number-crunching   |
| **Concurrent**     | asyncio / Node event loop    | multi-threaded server on cores |

### Coffee-shop analogy
- Concurrency = one barista juggling many orders by switching whenever a drink is *waiting*
  (espresso machine running). Many orders in progress; one action at any instant. Shines
  when tasks **wait**.
- Parallelism = two baristas making drinks simultaneously. Needs two workers (cores).

### The classic question: single-threaded asyncio/Node — concurrent, parallel, both, neither?
**Concurrent, not parallel.** The event loop interleaves tasks — while one `await`s I/O
(blocked, waiting), the loop progresses another; thousands in flight (concurrency). Single
thread → one thing runs at any instant (not parallel). Ideal because web workloads are
**I/O-bound** (mostly waiting). Parallelism is only needed for **CPU-bound** work.

## Hazards
- **Race condition** — outcome depends on timing of unsynchronized access to shared mutable
  state. (Note: this is a *hazard under* concurrency, NOT the definition of concurrency.)
- **Deadlock** — circular waiting (see topic 5).
- **Livelock** — tasks keep reacting to each other, no progress.
- **Starvation** — a task never gets the resource (unfair scheduling).
- Framing: **race condition = too little synchronization; deadlock = too much / badly-ordered
  synchronization.** Locks fix races but introduce deadlock risk — that's the tension.

## Primitives
Mutex/lock (mutual exclusion) · RW lock (many readers / one writer) · semaphore (N permits —
bounded concurrency) · condition variable (wait for a predicate) · atomics/CAS (lock-free
simple updates).

## Memory model (senior)
**Visibility** (a write may not be seen by another thread without a memory barrier) and
**reordering** (compiler/CPU reorder instructions; happens-before relationships guarantee
ordering).

## Thread pool vs thread-per-request
- **Thread-per-request:** thread creation cost + ~1MB stack each (10k requests ≈ 10GB) +
  context-switch thrashing + **no backpressure** (spike → crash).
- **Thread pool:** amortized threads + **bounded concurrency = backpressure** (extra work
  queues or is rejected with 503 → graceful degradation). *A bounded pool is a backpressure
  mechanism* — the key senior point.
- **Sizing:** CPU-bound ≈ #cores (more just adds switching overhead); I/O-bound ≫ cores
  (threads mostly blocked-waiting; `threads ≈ cores × (1 + wait/compute)`), or use async.
- Tradeoffs: queue management (bounded vs unbounded — unbounded just moves the crash to
  memory), rejection policy, pool starvation/deadlock (pooled tasks blocking on pooled
  tasks), head-of-line blocking (one slow task holds a slot — your synchronous-LLM
  bottleneck).
- **Modern footnote:** virtual threads (Java 21 / Loom) and goroutines are cheap enough to
  make thread-per-request viable again — blocking-style code with event-loop scalability.

## Optimistic vs pessimistic concurrency control
- **Pessimistic:** lock first (SELECT FOR UPDATE). **Optimistic:** version/constraint, fail
  and retry on conflict. ClientLens uses optimistic (the unique constraint — let the race
  happen, one loser fails cleanly).

## How ClientLens does it
- **Async I/O concurrency** on the request path + inside each worker (FastAPI/asyncio — one
  loop, many awaits, no thread-per-request). All I/O-bound (MySQL, Kafka, LLM API).
- **Parallelism via processes:** each worker is a separate container/process (own
  interpreter, own GIL); scale by replicas (ai-worker×10); Kafka **partitions** distribute
  work across consumers. So parallelism lives at the **deployment layer**, not Python
  threading.
- The only lock in the codebase: the mock CRM store's `threading.Lock`, guarding shared dicts
  against Uvicorn's threadpool (defensive against a race condition — not threads-for-
  parallelism).

## Soundbite
"A single asyncio process is concurrent but not parallel; parallelism comes from running
multiple worker processes/replicas with Kafka partitions distributing the work."

---

# 5. Python + Deadlock

## Part A — Python's concurrency model & the GIL

### The GIL (they WILL ask)
- **What:** the Global Interpreter Lock is a mutex in CPython that lets only **one thread
  execute Python bytecode at a time, per process**. Many threads can exist and the OS
  switches between them, but only one holds the interpreter at any instant.
- **Why it exists:** CPython uses **reference counting** for memory; concurrent refcount
  updates would race → corruption. The GIL is the coarse fix (also gives fast single-thread
  execution + simple C-extension integration). A deliberate tradeoff.
- **Problem:** CPU-bound multithreading gets ~**1×** (sometimes worse — GIL contention +
  context switches). Threads can't run Python bytecode in parallel.
- **But I/O-bound is fine:** a thread **releases the GIL while waiting on I/O**, so others run
  during the wait. That's why threads (and asyncio) work for I/O concurrency.
- **Rule:** I/O-bound → threads or asyncio OK; CPU-bound → threads useless.

### Workarounds for CPU-bound Python
1. **Multiprocessing** (`multiprocessing` / `concurrent.futures.ProcessPoolExecutor`) — each
   process has its **own interpreter + own GIL** → real parallelism on multiple cores. Cost:
   no shared memory by default (args/results **pickled** across process boundary — IPC
   overhead), higher memory. Go-to for CPU work.
2. **Native/C extensions that release the GIL** — NumPy/pandas/Cython do heavy work in C and
   release the GIL → real parallelism even with threads. Free win for numeric work.
3. **Offload / free-threaded CPython** — Rust/C bindings; PEP 703 makes the GIL optional in
   3.13+ (experimental — mention to show currency).

```python
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
# CPU-bound → ProcessPoolExecutor (real parallelism, dodges the GIL)
# I/O-bound → ThreadPoolExecutor  (concurrency; GIL released during I/O)

def heavy(n): return sum(i*i for i in range(n))

with ProcessPoolExecutor(max_workers=4) as ex:
    results = list(ex.map(heavy, [10_000_000]*4))   # 4 cores, truly parallel
```

### asyncio (your stack)
Single-threaded **event loop**, cooperative multitasking via `async`/`await`. No preemption →
no data races on shared memory *between awaits*. BUT a blocking call (or `time.sleep`) freezes
the whole loop → must use async libs (`asyncmy`, `asyncpg`, `aiokafka`) or offload with
`run_in_executor`.

### "Does the GIL prevent deadlocks?" → **No.**
The GIL serializes bytecode execution, not your logic. Your `threading.Lock`s are separate;
two threads can still each hold a lock and wait on the other. Common misconception.

### Does adding threads to a CPU-bound Python program make it faster? → **No.**
Because of the GIL, CPU-bound threads take turns holding the interpreter — ~1× speedup, often
slightly worse (contention + switching). I/O-bound would improve (GIL released during waits).
Fix: multiprocessing or a C extension.

## Part B — Deadlock (theory)

### What it is
Two or more tasks each waiting for a resource the other holds → a cycle → frozen forever
(not crashed). Classic: two threads acquiring two locks in **opposite order**.

```python
import threading
lock1, lock2 = threading.Lock(), threading.Lock()
def a():
    with lock1:
        with lock2: ...   # waits for lock2 (held by b)
def b():
    with lock2:
        with lock1: ...   # waits for lock1 (held by a) → deadlock
```

### The four Coffman conditions (ALL required — break any ONE to prevent)
1. **Mutual exclusion** — resource held exclusively.
2. **Hold and wait** — hold one resource while waiting for another.
3. **No preemption** — can't be forcibly taken; released only voluntarily.
4. **Circular wait** — a cycle of waiters (A→B→A).

### Prevention / handling
- **Lock ordering** (breaks circular wait) — global acquisition order; everyone acquires in
  the same order. *Give this first.*
- **Lock timeouts** — `lock.acquire(timeout=...)`; on failure release all + retry.
- **Acquire all at once** — grab everything or nothing.
- **Detection + recovery** — detect the cycle, abort one participant. What **databases** do:
  detect deadlock, kill one transaction, caller retries.
- **Avoid shared locks** — immutability / message passing / single-owner data.

### Python-specific deadlock flavors
- **Thread deadlock** — the two-lock case above (GIL does NOT save you).
- **Self-deadlock** — `threading.Lock` is **non-reentrant**; the *same thread* re-acquiring a
  lock it holds deadlocks with itself. Fix: **`threading.RLock`** (reentrant).
- **asyncio** — awaiting a future/event that never completes; a coroutine holding an
  `asyncio.Lock` and awaiting another that needs it; **blocking the event loop** (sync
  blocking call freezes everything — same symptom); connection-pool starvation.
- **Database** — two txns lock rows in opposite order; DB detects + kills one. Relevant to
  ClientLens's concurrent workers → keep txns short, consistent access order, optimistic
  unique-constraint so duplicates fail fast instead of holding locks.

### Deadlock vs livelock vs starvation vs race condition
- **Deadlock** — everyone stuck waiting, forever.
- **Livelock** — actively reacting, no progress (two people dodging in a hallway).
- **Starvation** — a task never gets the resource (others jump ahead).
- **Race condition** — *different* bug: timing-dependent unsynchronized access.

## Python concepts they might probe (concept, not syntax)
Decorator (wrap a function — `@lru_cache`, logging) · generator (`yield`, lazy iterator) ·
context manager (`with` — deterministic setup/teardown) · duck typing / Protocols · GC
(reference counting + cycle collector).

## Soundbites
- "The GIL lets only one thread run Python bytecode at a time; threads don't speed up
  CPU-bound work but are fine for I/O since the GIL is released while waiting. CPU work →
  multiprocessing (own GIL per process)."
- "A deadlock needs all four Coffman conditions; break one — usually with consistent lock
  ordering. The GIL does not prevent deadlocks."
- "`threading.Lock` is non-reentrant — use `RLock` to avoid self-deadlock."

---

# 6. SQL

## ACID
- **Atomicity** — all-or-nothing; fully commit or fully roll back.
- **Consistency** — moves the DB from one **valid state to another**, respecting all
  constraints/FKs/triggers; never leaves an invariant violated. (This is *DB* consistency —
  NOT distributed "eventual consistency"; don't conflate.)
- **Isolation** — concurrent transactions don't interfere; result is as if run in some serial
  order, to a degree set by the **isolation level**.
- **Durability** — committed data survives crashes/restarts (WAL / durable storage).

## Isolation levels (weak → strong) + anomalies prevented
- **Read Uncommitted** — dirty reads possible.
- **Read Committed** — no dirty reads.
- **Repeatable Read** — no non-repeatable reads. (InnoDB/MySQL default.)
- **Serializable** — no phantom reads; fully isolated (costliest).
Anomalies: **dirty read** (read uncommitted data) · **non-repeatable read** (same row read
twice differs) · **phantom read** (range query returns new rows on re-read).

## Other essentials
- **Indexing:** speeds reads, slows writes, costs storage. **Composite index leftmost-prefix
  rule.** B-tree vs hash; covering index.
- **Joins:** inner/left/right/full; a join often beats N queries.
- **N+1 problem:** loop over parents + one child query each → fix with a join / eager load.
- **Normalization** (reduce redundancy) vs **denormalization** (read performance) — tradeoff.
- **Transactions:** keep short (lock duration).
- **SQL injection:** always parameterize; never string-concat user input.

## Outbox → which ACID property, and why it breaks without it
Relies most on **Atomicity**. The outbox does **two writes** — business row (meeting) + event
row — that must happen **together or not at all**. Without atomicity, a crash between them:
- meeting saved, event lost → never processed (silent loss), OR
- event saved, meeting missing → "ghost event" → worker fails.
One atomic transaction eliminates both windows.

**Name the dual-write problem:**
> "The outbox solves the dual-write problem: you can't atomically write to MySQL AND publish
> to Kafka in one transaction. So you atomically write the business row + an outbox row in the
> same DB transaction, and a separate publisher relays the outbox to Kafka. Atomicity within
> one database replaces the impossible cross-system atomic write."

## How ClientLens does it
- Outbox = ACID atomicity in action (meeting + event in one txn); idempotency marker + work
  share a txn.
- **UNIQUE (event_id, consumer_name)** = a constraint used as a *concurrency-control*
  mechanism enforcing idempotency (SQL ↔ concurrency ↔ idempotency).
- Indexes on `tenant_id`, `meeting_id`, `client_id` (every query filters by tenant).
- **Multi-tenancy:** shared-schema + `WHERE tenant_id` (`TenantScopedRepository`).
  Alternatives: schema-per-tenant, DB-per-tenant (isolation vs ops cost — ADR-008).
- Parameterized queries via SQLAlchemy (no injection).

## Likely follow-ups
- "Which isolation level and why?" → Read Committed / Repeatable Read for most OLTP;
  Serializable only when truly needed (costly).
- "Debug a slow query?" → EXPLAIN plan; check index usage; look for full scans / N+1.
- "When denormalize?" → read-heavy, join cost dominates; accept write complexity + possible
  inconsistency.

---

# 7. Testing

## Know
- **Test pyramid:** many fast unit > fewer integration > few e2e (slow, brittle).
- **Test doubles (precise names):**
  - **Dummy** — filler, unused.
  - **Stub** — canned answers to drive a path.
  - **Fake** — working but simplified implementation (in-memory).
  - **Mock** — verifies *interactions* (was X called with Y?).
  - **Spy** — records calls for later assertions.
- **Good test:** fast, isolated, deterministic, one reason to fail, readable.
- **TDD:** red → green → refactor. **AAA:** Arrange, Act, Assert.
- **Design for testability:** DI, pure functions, inject the clock.

## Testing time-dependent code — "inject the clock" (key technique)
Don't call the system clock directly inside the unit under test. **Inject a clock dependency**
(a callable returning time). Production passes the real clock; tests pass a **fake clock**
they advance manually → simulate elapsed time instantly.

```python
class FakeClock:
    def __init__(self): self.t = 0.0
    def __call__(self): return self.t
    def advance(self, s): self.t += s

clock = FakeClock()
cb = CircuitBreaker(reset_timeout=30.0, clock=clock)
cb.record_failure()          # OPEN
clock.advance(30.0)          # "30s pass" — instant, no real waiting
assert cb.state is CircuitState.HALF_OPEN
```
Principles it demonstrates: **determinism** (time/randomness/I/O are the 3 sources of flaky
tests — inject them) and **design for testability = Dependency Inversion applied to time**
(depend on a `clock` abstraction, not the `time` module). A test that *sleeps* is slow AND
still timing-dependent (flaky on loaded CI).

Alternatives: monkeypatch/mock (`unittest.mock.patch`, `freezegun`) — works but patches global
state, more brittle; injection is cleaner (explicit).
**General rule:** "test something depending on time/randomness/network?" → inject it and
substitute a controllable fake.

## How ClientLens does it
- **Pyramid:** pure-core worker tests (unit, no Kafka) > repo/API tests (integration, real
  MySQL) > manual live e2e smoke.
- **Doubles:** `InMemoryEventBus`, `MockLLMProvider`, `FakeClock` = **fakes**;
  `AlwaysFailProvider`, `TransientFailCRM` = **stubs**.
- **Testability by design:** pure-core/loop split tests logic without a broker; injectable
  clock tests timeouts without sleeping.
- **Isolation:** conftest truncates tables between tests.
- **Idempotency test:** call the handler twice, assert one effect + one marker.

## [bridge]
JUnit + Mockito = pytest + `unittest.mock`/fakes. `@Mock` = a mock; a hand-written in-memory
impl = a fake. Java `Clock.fixed()` = the injectable-clock idea in the JDK.

## Likely follow-ups
- "Test time-dependent code?" → inject the clock.
- "Test a Kafka consumer without Kafka?" → separate pure logic from transport.
- "Mock vs stub vs fake?" → interaction-verifier / canned-answer / working-simplified-impl.
- "What NOT to test?" → trivial getters, framework internals; test behavior, not
  implementation details (brittle).

---

# 8. Frontend (React + TypeScript)

## Know
- **Component model:** UI = f(state, props); re-render when state/props change.
- **State vs props:** props = read-only inputs from parent; state = internal, mutable via
  setter.
- **Server state vs client state (THE senior point):** don't duplicate server data in a
  client store; cache it in a query layer (TanStack Query) with the server as source of
  truth. Client state = UI-only (form inputs, toggles).
- **Hooks:** `useState`, `useEffect` (side effects + deps array + cleanup), `useMemo`/
  `useCallback` (memoize), custom hooks (reuse logic). Rules: top-level, unconditional,
  stable deps.
- **Controlled components:** input `value` + `onChange` → state is single source of truth
  (vs uncontrolled/refs).
- **Keys in lists:** stable, unique (NOT array index) — correct reconciliation.
- **Data fetching:** `useQuery` (reads, cached by key) vs `useMutation` (writes) +
  `invalidateQueries`.
- **TypeScript:** `type` vs `interface`; **generics** (`apiGet<T>`); `unknown` vs `any`
  (prefer `unknown` — forces narrowing); union/discriminated unions; `strict` mode.

## The invalidate→refetch mechanism (name the 3 parts)
1. **Read = cached query keyed by name:** `useQuery({ queryKey: ["clients"] })`.
2. **Write = mutation that invalidates the key:** in `onSuccess`,
   `queryClient.invalidateQueries({ queryKey: ["clients"] })`.
3. **Invalidation is the trigger:** marks `["clients"]` stale → Query **auto-refetches** →
   fresh data → component re-renders.

**Money line:** "The mutation doesn't update the UI directly — it invalidates the cache, and
the cache drives the UI."

### Why better than manually pushing to a local array
1. Server sets fields you don't have (`id`, `created_at`, defaults) → refetch gets the
   **canonical** representation.
2. Avoids **two-sources-of-truth drift** (local copy vs server) — classic stale bug.
3. Picks up **concurrent changes** (another user/tab) a local push would miss.
4. Less code, fewer bugs.

### Tradeoff (senior nuance)
Invalidate+refetch costs a **network round-trip** (brief delay). Alternative: **optimistic
update** — update cache immediately, reconcile/rollback if the server rejects (snappier, more
complex). Know when to use which (invalidate = simple + always correct; optimistic = fast +
more code).

## How ClientLens does it
- `main.tsx`: "TanStack Query manages SERVER state; we don't duplicate it in a global store."
- `useClients` (`useQuery`, key `["clients"]`) for reads; `useCreateClient` (`useMutation` →
  `onSuccess` invalidates) for writes → list auto-refreshes, no reload.
- Controlled form input; `key={c.id}` in the list; `apiGet<T>`/`apiPost<T>` are generics;
  request body typed `unknown` (safe).

## [bridge]
Angular → React: React is a library not a framework; JSX vs templates; hooks vs services/DI;
TanStack Query ≈ a caching data service as single source (vs each component hoarding stale
server-data copies).

## Likely follow-ups
- "Why not put server data in Redux?" → duplication → staleness/sync bugs.
- "What triggers a re-render?" → state/prop (and context) change; `key` change remounts.
- "useEffect pitfalls?" → missing deps (stale closures), missing cleanup (leaks), running too
  often.
- "type vs interface?" → interface for object shapes/extension; type for unions/primitives/
  aliases.

---

# Bonus: Sorting in JavaScript (came up in prep)

## The basics
`Array.prototype.sort()` sorts **in place** (mutates) and returns the array. **By default it
sorts as strings** (UTF-16 code-unit order) — the #1 gotcha.

```js
[1, 2, 10, 21].sort();               // → [1, 10, 2, 21]  ❌ string sort
[1, 2, 10, 21].sort((a, b) => a - b);// → [1, 2, 10, 21]  ✓ numeric ascending
[1, 2, 10, 21].sort((a, b) => b - a);// → [21, 10, 2, 1]  ✓ descending
```

## Comparator contract
`(a, b) => number`: **negative** → a before b; **positive** → a after b; **zero** → equal.
`a - b` works for numbers (ascending). For non-numbers use explicit compare or `localeCompare`.
**Bug:** returning a boolean (`a > b`) coerces to 1/0 — never negative → broken order. Always
return a number.

## Strings
Default code-unit order mishandles case (`"Z"` < `"a"`) and locales. Use **`localeCompare`**:
```js
["banana","Apple","cherry"].sort((a, b) => a.localeCompare(b));
```
For large arrays, reuse `Intl.Collator`: `arr.sort(new Intl.Collator("en").compare)`.

## Mutation & the modern fix
`sort()` mutates — a bug if you sort React state/props directly. **ES2023 `toSorted()`**
returns a new array:
```js
const sorted = arr.toSorted((a, b) => a - b);   // arr unchanged
const sorted2 = [...arr].sort((a, b) => a - b);  // older non-mutating idiom
```

## Stability & algorithm
- **Stable since ES2019** — equal elements keep original order (enables multi-key sorting).
- Multi-key: `objs.sort((a,b) => a.age - b.age || a.name.localeCompare(b.name))` — first
  non-zero comparison wins.
- V8 (Chrome/Node) uses **TimSort** (stable, adaptive), **O(n log n)**. Keep comparators cheap
  (called O(n log n) times).

## Soundbites
- "Default sort is lexicographic — `[1,10,2]` — always pass a comparator for numbers; `a - b`
  is ascending."
- "`sort()` mutates; use `toSorted()` (ES2023) or `[...arr].sort()` — matters in React."
- "Stable since ES2019; V8 uses TimSort, O(n log n)."

---

# Cross-topic synthesis (say these — they signal seniority)
- Idempotency is enforced by a **SQL** unique constraint, which is a **concurrency**-control
  mechanism, protecting an **at-least-once** messaging pipeline.
- **202 Accepted** is a REST status code chosen to *reflect* the async/concurrency design;
  the frontend consequence is **status polling** (`refetchInterval`).
- The **GIL** is *why* CPU-heavy work runs in separate processes, not threads.
- **Dependency Inversion (SOLID)** is *why* testing is easy — inject fakes / inject the clock.
- **Exactly-once effect** = at-least-once delivery + idempotent consumer + outbox (atomic
  write+publish).
- **Race condition = too little synchronization; deadlock = too much / badly-ordered.**

# Delivery tips (theoretical interview, no live coding)
- Structure: definition → why/tradeoff → concrete example → failure mode.
- Volunteer the tradeoff and failure mode unprompted.
- Use the Java background openly: "In Java I'd do X; the Python equivalent is Y" — shows
  transferable seniority (what a "we'll train you" employer screens for).
- If unsure, reason from principles out loud rather than bluffing.
