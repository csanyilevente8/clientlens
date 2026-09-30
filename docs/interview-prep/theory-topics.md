# Senior Interview Prep — Theory Topics

Format: 45 min theory (no live coding) + 30 min system design. Stack: Python + React.
Background note: your Java/Angular experience is an asset — they hire for engineering
reasoning and will train the stack. Lead from principles, then bridge to Python/React
(and Java where it scores points). Java→Python bridges are marked **[bridge]**.

Every topic ends with **"how ClientLens does it"** so answers are concrete, and **likely
follow-ups** so you rehearse the second "why?".

---

## 1. SOLID / OOP

### Core OOP
- **Encapsulation** — hide internal state; expose behavior. Invariants stay valid.
- **Abstraction** — expose *what*, hide *how* (interface vs implementation).
- **Inheritance** — reuse via is-a. Prefer **composition over inheritance** (inheritance
  couples tightly; composition is flexible). Senior signal: say this unprompted.
- **Polymorphism** — same interface, many implementations, chosen at runtime.

### SOLID
- **S — Single Responsibility:** one reason to change. *Split logic from transport.*
- **O — Open/Closed:** extend without modifying. *Add a case without editing callers.*
- **L — Liskov Substitution:** a subtype must work anywhere the base does (no surprises,
  no strengthened preconditions / weakened postconditions).
- **I — Interface Segregation:** many small interfaces > one fat one; don't force
  clients to depend on methods they don't use.
- **D — Dependency Inversion:** depend on abstractions, not concretions; inject deps.

**[bridge]** Java `interface` = Python `Protocol` (structural/duck typing — a class
conforms by shape, no `implements` keyword). Spring `@Autowired` DI = constructor
injection / FastAPI `Depends`.

### How ClientLens does it
- **S:** workers split the pure core (`handle_meeting_created`) from the Kafka loop
  (`run_ai_worker`) — processing vs transport. Also why the core is unit-testable.
- **O:** `get_llm_provider()` factory — adding Anthropic = new class + one branch, no
  business-logic change. Same for `CRMClient`, `EmbeddingProvider`.
- **L:** any `LLMProvider` (Mock / real) is interchangeable; Mock honors the same contract.
- **I:** small `Protocol`s — `LLMProvider`, `CRMClient`, `EventBus`, `EmbeddingProvider`.
- **D:** business code depends on the `CRMClient` protocol, never on httpx; `HTTPCRMClient`
  is injected.
- **Best example:** `TenantScopedRepository[ModelT: Base]` — generic base + 2-line
  subclasses. Encapsulates the tenant filter so callers *can't* forget it ("the safe
  path is the default path").

### Likely follow-ups
- "Inheritance vs composition?" → composition is looser coupling; inheritance for true
  is-a only. Overuse of inheritance → fragile base class problem.
- "Give an LSP violation." → `Square extends Rectangle` where `setWidth` also changes
  height, breaking callers who assume independent dimensions.
- "How is DI different from a service locator?" → DI pushes deps in (testable, explicit);
  service locator pulls them (hidden deps, harder to test).

---

## 2. REST API

### Know
- **Resources + verbs:** GET (read), POST (create/action), PUT (replace), PATCH (partial),
  DELETE.
- **Status codes:** 200 OK, 201 Created, 202 Accepted (async!), 204 No Content, 400 bad
  request, 401 unauthenticated, 403 unauthorized, 404 not found, 409 conflict, 422
  validation, 429 rate limit, 500 server, 503 unavailable.
- **Statelessness:** no server session; each request self-contained (e.g. JWT) → any
  replica serves any request → horizontal scaling.
- **Method safety & idempotency (spec):** GET/HEAD safe (no side effects); GET/PUT/DELETE
  idempotent; **POST is NOT** → needs idempotency keys for safe retries.
- **Versioning:** URL (`/api/v1`, explicit, cache-friendly) vs header/content-negotiation
  (clean URLs). Tradeoff = explicitness vs URL purity.
- **Idempotency of PUT vs POST:** PUT to a known URI replaces → same result if repeated;
  POST creates a new resource each time unless deduped.

### How ClientLens does it
- `POST /clients` → **201**. `POST /meetings` → **202 Accepted** (deliberate: processing
  is async — the status code reflects the event-driven design).
- `GET /clients/{id}` → 200 or **404** even for another tenant's real id (don't leak
  existence).
- `DELETE` → **204**. Stateless auth via JWT (RS256; workers/MCP verify with public key).
- `/api/v1/...` URL versioning.

### Likely follow-ups
- "Is POST idempotent? How to make double-submit safe?" → no; idempotency key (Stripe-
  style; your mock CRM `Idempotency-Key`).
- "200 vs 201 vs 202?" → done+here / created / accepted-but-not-done-yet.
- "REST vs RPC vs GraphQL?" → REST = resources+verbs, cacheable, over-/under-fetch risk;
  GraphQL = client shapes the query, one endpoint, harder caching; RPC = action-oriented.
- "How do you handle partial failure in a REST call to a flaky dependency?" → timeouts,
  retries with backoff, circuit breaker, idempotency keys.

---

## 3. Idempotency

### Know (the causal chain — memorize)
> Distributed systems → network failures → must retry → at-least-once delivery →
> duplicates → **need idempotency** (make duplicates harmless).

- **Definition:** N applications have the same effect as 1.
- **Exactly-once *delivery* is impossible** (Two Generals: sender can't tell if the
  message or the ack was lost → resend=duplicate, or don't=loss). You choose:
  - **at-most-once** (tolerate loss), **at-least-once** (tolerate duplicates),
    exactly-once delivery = myth.
- **Exactly-once *effect*** = at-least-once delivery + idempotent (or transactional)
  consumer. That's what "Kafka exactly-once" really means.
- **Idempotency ≠ commutativity** (order-independence) ≠ safety (no side effects).
- Effect, not response: a replay may return a different status (201 then 200) but the
  *state* is unchanged.

### How ClientLens does it
- `processed_events` with **UNIQUE (event_id, consumer_name)**. Two layers: app-level
  check (fast path) + DB unique constraint (correctness under concurrent duplicates —
  the loser gets `IntegrityError`, rolls back). *App check = optimization; constraint =
  guarantee.*
- Marker written **in the same transaction as the work** → "done" and "marked done" never
  disagree.
- Keyed per-consumer because one event has **3 consumers** (AI, index, CRM) — each tracks
  its own processing.
- **Cross-store idempotency (advanced):** index worker's marker is in MySQL, chunks in
  pgvector (no shared txn). Solved by making the *work* idempotent (delete-then-insert) +
  ordering writes → effectively-once without a distributed transaction.
- **HTTP layer:** mock CRM dedupes on `Idempotency-Key`; stable key = `event_id:item_id`
  so retries never duplicate CRM tasks.

### Likely follow-ups
- "Two workers get the same message at once — what happens?" → both try to insert the
  marker; unique constraint lets one win, other gets IntegrityError → rolls back.
- "Why not exactly-once delivery?" → Two Generals; you get exactly-once effect.
- "Where do you store the idempotency key and for how long?" → durable store; TTL/retention
  tradeoff (keep long enough to cover max retry/redelivery window).

---

## 4. Concurrency & Multithreading

### Know
- **Concurrency ≠ parallelism:** concurrency = structure (tasks interleave); parallelism
  = simultaneous execution (needs multiple cores). Async I/O = concurrency without
  parallelism.
- **The core problem:** shared mutable state + no coordination = race condition.
- **Hazards:**
  - **Race condition** — result depends on timing.
  - **Deadlock** — circular waiting (see topic 5 for the 4 conditions).
  - **Livelock** — threads react to each other, no progress.
  - **Starvation** — a thread never gets the resource.
- **Primitives:** mutex/lock (mutual exclusion), RW lock (many readers/one writer),
  semaphore (N permits — bounded concurrency), condition variable (wait for predicate),
  atomics/CAS (lock-free simple updates).
- **Memory model (senior):** **visibility** (a write may not be seen without a barrier),
  **reordering** (compiler/CPU reorder; happens-before gives ordering guarantees).
- **Why "just add locks" is naive:** contention, context-switch cost, coarse locks kill
  throughput, fine locks invite deadlock. Better: avoid shared mutable state (immutability,
  message passing, thread confinement).
- **Thread pool vs thread-per-request:** thread-per-request = creation cost + ~1MB stack
  each + context-switch thrashing + no backpressure. Pool = amortized threads + **bounded
  concurrency = backpressure** (queue or reject under overload). Sizing: CPU-bound ≈ cores;
  I/O-bound ≫ cores (threads mostly blocked) — or use async instead.

**[bridge]** JVM threads = true parallelism; Python threads = GIL-limited (topic 5).
`synchronized`/`ReentrantLock` = `threading.Lock`/`RLock`. `CompletableFuture` = `asyncio`.

### How ClientLens does it
- **Async I/O concurrency** on the request path (FastAPI/asyncio — one loop, many awaits,
  no thread-per-request). **Process parallelism** for workers (Kafka partitions → parallel
  consumers; ai-worker scales to 10 replicas).
- Concurrency control for idempotency = DB unique constraint (**optimistic** — let the race
  happen, one loser fails cleanly). Circuit breaker guards a flaky downstream.

### Likely follow-ups
- "Optimistic vs pessimistic locking?" → pessimistic locks first (SELECT FOR UPDATE);
  optimistic uses a version/constraint and fails-retries on conflict. Yours is optimistic.
- "How size a thread pool?" → CPU-bound ~#cores; I/O-bound larger (Little's Law: depends on
  wait/compute ratio); or go async for heavy I/O.
- "Async vs threads?" → async = cooperative, single thread, no preemption (no data races
  between awaits) but a blocking call freezes the loop; threads = preemptive, need locks.

---

## 5. Python + Deadlock

### The GIL (they WILL ask) — expanded

**What it is:** the **Global Interpreter Lock** is a mutex in CPython that lets only **one
thread execute Python bytecode at a time, per process**. You can have many threads and the
OS switches between them, but only one holds the interpreter at any instant. (So it's not
"single-threaded" — it's "one thread runs Python at a time".)

**Why it exists:** CPython manages memory with **reference counting**. Concurrent
increments/decrements of the same refcount would race → memory corruption. The GIL is the
coarse, pragmatic fix: one lock protects the interpreter so refcounting is safe. Bonus: fast
single-threaded execution + simple C-extension integration. It's a deliberate tradeoff.

**The problem it causes:**
- **CPU-bound multithreading gets ~no speedup** — 4 threads on a heavy computation ≈ 1×
  (sometimes worse, due to GIL contention + context switches). Threads can't run Python
  bytecode in parallel.
- **I/O-bound work is fine** — a thread **releases the GIL while waiting** on I/O
  (network/disk/sleep), so other threads run during the wait. This is *why* threads (and
  asyncio) work well for I/O concurrency in Python.

**Rule:** I/O-bound → threads or asyncio OK; CPU-bound → threads useless.

**Workarounds for CPU-bound Python (know all three):**
1. **Multiprocessing** (`multiprocessing` / `ProcessPoolExecutor`) — the go-to. Each process
   has its **own interpreter + own GIL** → real parallelism on multiple cores. Cost: no
   shared memory by default (pickling/IPC), higher memory.
2. **Native/C extensions that release the GIL** — NumPy/pandas/Cython do heavy work in C and
   release the GIL, giving real parallelism even with threads. Free win for numeric work.
3. **Offload / different interpreter** — Rust/C bindings; or PEP 703 "free-threaded" CPython
   3.13+ makes the GIL optional (experimental — mention to show you're current).

**Crisp answer to memorize:**
> "The GIL is a mutex in CPython that lets only one thread run Python bytecode at a time,
> needed to make reference-counting thread-safe. So threads don't speed up CPU-bound work —
> they serialize on the GIL — but I/O-bound work is fine because a thread releases the GIL
> while waiting. For CPU-bound work I use multiprocessing (own GIL per process) or a C
> extension like NumPy that releases the GIL. That's why my project runs workers as separate
> processes."

- **[bridge]** Java threads give true CPU parallelism → a thread pool is the natural tool
  for parallel compute. In Python, because of the GIL, the equivalent instinct is a
  **process** pool for CPU work; threads are only for I/O. That's *why ClientLens scales
  workers as separate processes/containers* — the GIL is per-process, so separate processes
  sidestep it entirely.

### asyncio (your stack)
- Single-threaded **event loop**, cooperative multitasking via `async`/`await`.
- No preemption → no data races on shared memory *between awaits*.
- **But** a blocking call freezes the whole loop → must use async libs (`asyncmy`,
  `asyncpg`, `aiokafka`). CPU-heavy work must go to a process/executor.

### Deadlock — the four Coffman conditions (all required)
1. **Mutual exclusion** — resource held exclusively.
2. **Hold and wait** — hold one, wait for another.
3. **No preemption** — can't force-release.
4. **Circular wait** — cycle of waiters.
Break **any one** → no deadlock. Most practical: **lock ordering** (global acquisition
order) breaks circular wait.

- **Python thread deadlock:** two `threading.Lock`s acquired in opposite order by two
  threads. `RLock` (reentrant) avoids self-deadlock when one thread re-acquires its own
  lock.
- **asyncio flavor:** awaiting something that never completes; or **pool starvation** (task
  waits on another task that can't get a slot).
- **DB deadlock (relevant to you):** two transactions lock rows in opposite order → the DB
  detects it and kills one (deadlock error). Defense: short transactions, consistent access
  order, optimistic constraint approach (fail+retry, don't hold locks).

### Python concepts they might probe (concept, not syntax)
- **Decorator** — a function wrapping another (cross-cutting: logging, caching, `@lru_cache`).
- **Generator** — lazy iterator (`yield`); memory-efficient streaming.
- **Context manager** (`with`) — deterministic setup/teardown (resource safety).
- **Duck typing / Protocols** — structural interfaces.
- **GC** — reference counting + cycle collector.

---

## 6. SQL

### Know
- **ACID:** Atomicity (all-or-nothing), Consistency (constraints hold), Isolation
  (concurrent txns don't corrupt), Durability (committed = persisted).
- **Isolation levels** (weak→strong) + anomalies they prevent:
  - Read Uncommitted (dirty reads possible) → Read Committed (no dirty) → Repeatable Read
    (no non-repeatable reads; InnoDB default) → Serializable (no phantoms).
  - Anomalies: **dirty read**, **non-repeatable read**, **phantom read**.
- **Indexing:** speeds reads, slows writes, costs storage. **Composite index leftmost-prefix
  rule.** B-tree vs hash. Covering index.
- **Joins:** inner/left/right/full; know when a join beats N queries.
- **N+1 problem:** loop over parents, one child query each → fix with join/eager load.
- **Normalization** (reduce redundancy) vs **denormalization** (read performance). Know the
  tradeoff.
- **Transactions:** BEGIN/COMMIT/ROLLBACK; keep them short (lock duration).
- **SQL injection:** always parameterize; never string-concat user input.

### How ClientLens does it
- **Outbox = ACID atomicity in action:** meeting row + outbox event commit in ONE
  transaction → can't have one without the other. Idempotency marker + work also share a
  txn.
- **UNIQUE (event_id, consumer_name)** = a constraint used as a *concurrency-control*
  mechanism enforcing idempotency (SQL ↔ concurrency ↔ idempotency synthesis).
- **Indexes** on `tenant_id`, `meeting_id`, `client_id` (every query filters by tenant).
- **Multi-tenancy:** shared-schema + `WHERE tenant_id` (`TenantScopedRepository`).
  Alternatives: schema-per-tenant, DB-per-tenant (isolation vs ops cost — ADR-008).
- **Parameterized queries** via SQLAlchemy (no injection).

### Likely follow-ups
- "Which isolation level and why?" → Read Committed or Repeatable Read for most OLTP;
  Serializable only when you truly need it (costly).
- "How would you debug a slow query?" → EXPLAIN plan, check index usage, look for full
  scans / N+1.
- "When denormalize?" → read-heavy, join cost dominates; accept write complexity + possible
  inconsistency.

---

## 7. Testing

### Know
- **Test pyramid:** many unit (fast, isolated) > fewer integration > few e2e (slow, brittle).
- **Test doubles (use precise names):**
  - **Dummy** — filler, unused.
  - **Stub** — canned answers to drive a path.
  - **Fake** — working but simplified implementation (in-memory).
  - **Mock** — verifies *interactions* (was X called with Y?).
  - **Spy** — records calls for later assertions.
- **Good test:** fast, isolated, deterministic, one reason to fail, readable.
- **TDD:** red → green → refactor. AAA: Arrange, Act, Assert.
- **Design for testability:** dependency injection, pure functions, inject the clock.

**[bridge]** JUnit + Mockito = pytest + `unittest.mock`/fakes. `@Mock` = a mock; a hand-
written in-memory impl = a fake.

### How ClientLens does it
- **Pyramid:** pure-core worker tests (unit, no Kafka) > repo/API tests (integration, real
  MySQL) > manual live e2e smoke.
- **Doubles:** `InMemoryEventBus`, `MockLLMProvider`, `FakeClock` = **fakes**;
  `AlwaysFailProvider`, `TransientFailCRM` = **stubs**.
- **Testability by design:** pure-core/loop split lets you test logic without a broker; the
  breaker's **injectable clock** tests timeouts *without sleeping* (deterministic).
- **Isolation:** conftest truncates tables between tests.
- **Idempotency test:** call the handler twice, assert one effect + one marker.

### Likely follow-ups
- "How test time-dependent code?" → inject the clock (you did).
- "How test a Kafka consumer without Kafka?" → separate pure logic from transport.
- "Mock vs stub vs fake?" → interaction-verifier / canned-answer / working-simplified-impl.
- "What NOT to test?" → trivial getters, framework internals; don't test implementation
  details (brittle) — test behavior.

---

## 8. Frontend (React + TypeScript)

### Know
- **Component model:** UI = f(state, props). Components re-render when their state/props
  change.
- **State vs props:** props = inputs from parent (read-only); state = internal, mutable via
  setter.
- **Server state vs client state (THE senior point):** don't duplicate server data in a
  client store; cache it in a query layer (TanStack Query) with the server as source of
  truth. Client state = UI-only (form inputs, toggles).
- **Hooks:** `useState`, `useEffect` (side effects + dependency array + cleanup), `useMemo`/
  `useCallback` (memoize), custom hooks (reuse logic — composition). Rules: top-level,
  unconditional, stable deps.
- **Controlled components:** input `value` + `onChange` → state is single source of truth
  (vs uncontrolled/refs).
- **Keys in lists:** stable, unique (not array index) — for correct reconciliation.
- **Data fetching:** `useQuery` (reads, cached by key) vs `useMutation` (writes) +
  `invalidateQueries` (write→cache→auto-refetch→UI). Optimistic updates = next level.
- **TypeScript:** `type` vs `interface`; **generics** (`apiGet<T>`); `unknown` vs `any`
  (prefer `unknown` — forces narrowing); union/discriminated-union types; `strict` mode.

**[bridge]** Coming from Angular: React is less opinionated (library not framework); JSX vs
templates; hooks vs services/DI; TanStack Query ≈ avoiding stale DTOs / a caching layer.

### How ClientLens does it
- `main.tsx` comment: *"TanStack Query manages SERVER state; we don't duplicate it in a
  global store."*
- `useClients` (`useQuery`, key `["clients"]`) for reads; `useCreateClient`
  (`useMutation` → `onSuccess` invalidates `["clients"]`) for writes → list auto-refreshes,
  no reload. *The mutation doesn't touch the UI; it tells the cache data changed, and the
  cache drives the UI.*
- Controlled form input (`value` + `onChange`); `key={c.id}` in the list.
- `apiGet<T>`/`apiPost<T>` = **generics**; request body typed `unknown` (safe).

### Likely follow-ups
- "Why not put server data in Redux?" → duplication → staleness/sync bugs; Query caches +
  invalidates.
- "What triggers a re-render?" → state/prop change (and context). `key` change remounts.
- "useEffect pitfalls?" → missing deps (stale closures), missing cleanup (leaks), running
  too often.
- "type vs interface?" → interface for object shapes / extension; type for unions/
  primitives/aliases.

---

## Cross-topic synthesis (say these — they signal seniority)
- Idempotency is enforced by a **SQL** unique constraint, which is a **concurrency**-control
  mechanism, protecting an **at-least-once** messaging pipeline. (idempotency ↔ SQL ↔
  concurrency ↔ REST)
- **202 Accepted** is a REST status code chosen to *reflect* the async/concurrency design.
- The **GIL** is *why* CPU-heavy work runs in separate processes, not threads.
- **Dependency Inversion (SOLID)** is *why* testing is easy — inject fakes.
- **Exactly-once effect** = at-least-once delivery + idempotent consumer + outbox (atomic
  write+publish).

## Delivery tips for a theoretical interview
- Structure each answer: **definition → why/tradeoff → concrete example (ClientLens) →
  failure mode.**
- Volunteer the tradeoff and the failure mode without being asked.
- Use the Java background openly: *"In Java I'd do X; the Python equivalent is Y"* —
  demonstrates transferable seniority (which is what "we'll train you" hires for).
- If you don't know something: reason from principles out loud rather than bluffing.


---

# WEAK SPOTS — Detailed (from mock interview 2026-09-29)

These are the answers I fumbled in the mock. Drill these until automatic. Priority order:
concurrency-vs-parallelism (got backwards), then the rest.

---

## WS1. Concurrency vs Parallelism  ⚠️ TOP PRIORITY (I flipped the definitions)

### The definitions (memorize exactly)
- **Concurrency** = *dealing with* many things at once. A **structural** property of the
  code: tasks are interleaved and make progress over overlapping time periods. Does NOT
  require simultaneous execution — one CPU switching between tasks is concurrent.
- **Parallelism** = *doing* many things at once. **Simultaneous** execution — requires
  multiple cores/CPUs.

**Rob Pike one-liner (say this first, every time):**
> "Concurrency is about *dealing* with lots of things at once. Parallelism is about *doing*
> lots of things at once."

- Concurrency = property of the **design**. Parallelism = property of the **execution/
  hardware**.
- You can have: concurrency without parallelism (asyncio), parallelism without much
  concurrency (SIMD number-crunching), both (multi-threaded server on many cores), neither
  (a plain single-threaded script).

### Mistake I made
I defined concurrency as "modifications on the same state at the same time" — that's a
**race condition** (a *hazard under* concurrency), NOT concurrency itself. And I labeled I/O
as parallelism. Both wrong. Reset to Pike's line.

### The classic question: is single-threaded asyncio / Node concurrent, parallel, both,
neither?
**Answer: concurrent, but NOT parallel.**
- Concurrent: the event loop interleaves many tasks — while one request `await`s I/O
  (blocked, waiting), the loop progresses another. Thousands in flight, overlapping progress
  = concurrency.
- Not parallel: single thread → at any instant exactly one piece of code runs on the CPU.
- Works for servers because web workloads are **I/O-bound** (mostly waiting). You only need
  parallelism for **CPU-bound** work.

### The full-marks add-on
> "A single asyncio process is concurrent but not parallel. For parallelism I run multiple
> processes/replicas — which is what ClientLens does: async concurrency inside each worker,
> process-level parallelism across worker replicas and Kafka partitions."

**[bridge]** This is also why the GIL matters: even with threads, CPython gives concurrency
but not CPU parallelism → for CPU work use processes. Java threads give real parallelism, so
the calculus differs.

### YouTube search terms / channels
- Search: **"concurrency vs parallelism Rob Pike"** (his talk "Concurrency is not
  Parallelism" is the definitive source).
- Channel **Fireship** — search "concurrency vs parallelism" (short, punchy).
- Channel **ByteByteGo** — search "concurrency vs parallelism" (visual, interview-focused).

---

## WS2. Dependency Inversion Principle (definition slipped — said "size" not "direction")

### Precise definition (two halves)
1. High-level modules should not depend on low-level modules; **both depend on
   abstractions.**
2. Abstractions should not depend on details; **details depend on abstractions.**

The key word is **direction**, not size. Normally high-level code calls down into (and
depends on) low-level code. DIP **inverts** that: insert an interface that the high-level
module *owns*, and the low-level detail *conforms to it*. The dependency arrow now points at
the abstraction from both sides.

### DIP vs DI (name the distinction — senior signal)
- **DIP** = the principle ("depend on abstractions").
- **DI (dependency injection)** = the technique that supplies the concrete implementation
  (constructor injection, FastAPI `Depends`, Spring `@Autowired`).

### Concrete gains (have three ready — don't just say "flexibility")
1. **Testability** — inject a fake/in-memory implementation in tests (most compelling).
2. **Swappability** — change Postgres → MySQL without touching business logic.
3. **Decoupling / parallel work** — code against the interface independently.

### ClientLens
Business code depends on the `CRMClient` / `LLMProvider` **Protocol**, never on httpx or a
vendor SDK; the concrete client is injected. `get_llm_provider()` picks the impl.

### [bridge]
Java: interface + Spring `@Autowired`. Python: `Protocol` + constructor injection (structural
typing — conform by shape, no `implements`).

### YouTube search terms / channels
- Search: **"SOLID principles explained"** — channel **ByteByteGo** or **Fireship**
  ("SOLID in 100 seconds").
- Search: **"Dependency Inversion vs Dependency Injection"** (nails the DIP-vs-DI confusion).
- Channel **CodeAesthetic** — search "dependency injection" (excellent, principle-focused).

---

## WS3. REST 202 — the client-side consequence (I missed this half)

### The mechanism I missed
`201` = resource is done; body has the finished resource. `202` = accepted, **not done
yet** → the client cannot assume the result exists. It must treat **creation and completion
as two separate moments** and do one of:
1. **Poll a status endpoint** — `GET /meetings/{id}`, watch `status`: CREATED → PROCESSING →
   COMPLETED / FAILED. (ClientLens has a `status` column exactly for this; the frontend uses
   `refetchInterval` to poll while pending.)
2. **Be notified** — webhook / WebSocket / server-sent events push the "done" signal.

Spec note: a 202 response should point the client at where to monitor progress (status URL /
`Location`).

### Full answer shape
> "202 because processing is async — the server durably accepted the request and enqueues
> the work. The client can't assume the result exists on return; it polls a status endpoint
> (status field CREATED→COMPLETED) or gets notified via webhook/websocket. Creation and
> completion are two separate moments."

### YouTube search terms / channels
- Search: **"HTTP status codes explained"** — channel **ByteByteGo**.
- Search: **"202 Accepted vs 201 Created async API"**.
- Search: **"long running jobs REST API design polling vs webhook"**.

---

## WS4. ACID — Consistency & Isolation (I gave these thin definitions)

### All four, precisely
- **Atomicity** — all-or-nothing; a transaction fully commits or fully rolls back.
- **Consistency** — moves the DB from one **valid state to another**, respecting all
  constraints/FKs/triggers; never leaves an invariant violated. (This is *DB* consistency —
  constraints hold — NOT distributed "eventual consistency." Don't conflate them.)
- **Isolation** — concurrent transactions don't interfere; result is as if they ran in some
  serial order, to a degree set by the **isolation level**.
- **Durability** — once committed, data survives crashes/restarts (written to durable
  storage / WAL).

### Isolation levels (weak → strong) + anomalies prevented
- **Read Uncommitted** — dirty reads possible.
- **Read Committed** — no dirty reads.
- **Repeatable Read** — no non-repeatable reads. (InnoDB/MySQL default.)
- **Serializable** — no phantom reads; fully isolated (costliest).
Anomalies: **dirty read** (read uncommitted data), **non-repeatable read** (same row read
twice differs), **phantom read** (a range query returns new rows on re-read).

### Outbox → which property, and why it breaks without it
Relies most on **Atomicity**. The outbox does **two writes** — business row (meeting) + event
row — that must happen **together or not at all**. Without atomicity, a crash between them
gives:
- meeting saved, event lost → never processed (silent loss), or
- event saved, meeting missing → "ghost event" → worker fails.
One atomic transaction eliminates both windows.

**Senior line — name the "dual-write problem":**
> "The outbox solves the dual-write problem: you can't atomically write to MySQL AND publish
> to Kafka in one transaction. So instead you atomically write the business row + an outbox
> row in the same DB transaction, and a separate publisher relays the outbox to Kafka.
> Atomicity within one database replaces the impossible cross-system atomic write."

### YouTube search terms / channels
- Search: **"ACID properties explained"** — channel **ByteByteGo** or **Gaurav Sen**.
- Search: **"database isolation levels explained"** (dirty/non-repeatable/phantom reads).
- Search: **"transactional outbox pattern"** — channel **ByteByteGo** / **Gaurav Sen**.
- Search: **"dual write problem microservices"**.

---

## WS5. Testing time-dependent code — "inject the clock" (I blanked; I built this!)

### The technique
Don't call the system clock directly inside the unit under test. **Inject a clock
dependency** (a callable returning the time). Production passes the real clock; tests pass a
**fake clock** they advance manually → simulate elapsed time instantly.

```python
class FakeClock:
    def __init__(self): self.t = 0.0
    def __call__(self): return self.t
    def advance(self, s): self.t += s

clock = FakeClock()
cb = CircuitBreaker(reset_timeout=30.0, clock=clock)
cb.record_failure()                 # OPEN
clock.advance(30.0)                 # "30s pass" instantly
assert cb.state is CircuitState.HALF_OPEN
```
(That's `test_circuit_breaker.py` in my repo.)

### Why it's the right answer — name the principles
1. **Determinism** — time, randomness, and I/O are the 3 big sources of flaky tests; inject
   them to make tests reproducible. A test that *sleeps* is slow AND still timing-dependent
   (flaky on loaded CI).
2. **Design for testability = Dependency Inversion applied to time** — the breaker depends on
   a `clock` *abstraction*, not the concrete `time` module. (Cross-topic link: testing ↔
   SOLID.)

### Alternatives (breadth)
- Monkeypatch/mock (`unittest.mock.patch("time.monotonic")`, `freezegun`) — works but patches
  global state, more brittle. Injection is cleaner because it's explicit.
- **[bridge]** Java: inject `java.time.Clock` (has `Clock.fixed()`) instead of `Instant.now()`.

### General rule
"How do you test something depending on time / randomness / network?" → **inject it as a
dependency and substitute a controllable fake.**

### YouTube search terms / channels
- Search: **"dependency injection testable code"** — channel **CodeAesthetic**.
- Search: **"how to test time dependent code"** / **"testing with a fake clock"**.
- Search: **"test doubles mock stub fake spy"** — channel **ByteByteGo** (Martin Fowler's
  taxonomy).

---

## WS6. React — the invalidate→refetch mechanism (I gave principle, skipped mechanism)

### The three moving parts (name them)
1. **Read = a cached query keyed by name:** `useQuery({ queryKey: ["clients"] })` — result
   cached under `["clients"]`.
2. **Write = a mutation that invalidates that key:** `useMutation`, and in `onSuccess`:
   `queryClient.invalidateQueries({ queryKey: ["clients"] })`.
3. **Invalidation is the trigger:** marking `["clients"]` stale → Query **auto-refetches**
   active queries with that key → fresh server data → component re-renders.

**Money line:**
> "The mutation doesn't update the UI directly — it invalidates the cache, and the cache
> drives the UI."

### Why better than manually pushing to a local array
1. Server sets fields you don't have locally (`id`, `created_at`, defaults) → refetch gets
   the **canonical** representation.
2. Avoids **two-sources-of-truth drift** (local copy vs server) — the classic stale bug.
3. Picks up **concurrent changes** (another user/tab) that a local push would miss.
4. Less code, fewer bugs.

### The tradeoff (senior nuance)
Invalidate+refetch costs a **network round-trip** (brief delay). The alternative is an
**optimistic update** — update the cache immediately, reconcile/rollback if the server
rejects: snappier but more complex. Know when to use which (invalidate = simple + always
correct; optimistic = fast + more code).

### [bridge]
Angular: like relying on a caching data service as the single source, vs each component
hoarding its own server-data copy that goes stale.

### YouTube search terms / channels
- Search: **"TanStack Query / React Query invalidateQueries explained"**.
- Search: **"server state vs client state React"** — TkDodo (React Query maintainer) talks.
- Channel **Web Dev Simplified** or **Jack Herrington** — search "React Query tutorial".
- Search: **"React Query optimistic updates"** (for the tradeoff).

---

## Note on the YouTube links
I don't have web/YouTube access from this session, so the above are **search terms + trusted
channels** rather than direct URLs (I won't fabricate links that might be dead/wrong). The
channels named — **ByteByteGo, Fireship, CodeAesthetic, Gaurav Sen, Web Dev Simplified,
Jack Herrington, TkDodo** — are consistently high quality for these exact topics.
