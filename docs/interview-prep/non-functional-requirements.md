# Non-Functional Requirements (NFRs) — System Design Interview Cheat Sheet

**Functional requirements** = *what* the system does (features: "user can create a meeting").
**Non-functional requirements** = *how well* it does it (qualities: fast, reliable, secure,
scalable). NFRs are the "-ilities." In a 30-min system-design interview, **asking about NFRs
early** (before drawing boxes) is a strong senior signal — they drive every architectural
choice.

**How to use this in the interview:**
1. After clarifying functional scope, ask: "What are the constraints — scale, latency,
   consistency, availability?" Pin down *numbers*.
2. State which NFRs dominate for *this* problem (you can't maximize all — they trade off).
3. Justify each design decision by the NFR it serves and the tradeoff it accepts.

---

## The big list (the ones interviewers actually probe)

### 1. Scalability
- **What:** handle growth (more users/data/traffic) without redesign.
- **Vertical scaling** (bigger machine) vs **horizontal scaling** (more machines). Prefer
  horizontal for large scale; requires statelessness + partitioning.
- **Measure:** throughput at target load; behavior at 10x / 100x.
- **Tactics:** stateless services, load balancing, sharding/partitioning, caching,
  async/queues, read replicas, CDN, autoscaling.
- **Tradeoff:** distribution adds complexity (consistency, coordination, ops).
- **ClientLens:** API and workers scale **independently** (api×3, ai-worker×10); Kafka
  partitions distribute work; stateless JWT auth → any replica serves any request.

### 2. Availability
- **What:** the system is up and serving. Often the headline SLA.
- **Measure:** uptime %, "nines." **99.9%** ≈ 8.76 h/yr down; **99.99%** ≈ 52 min/yr;
  **99.999%** ≈ 5 min/yr. Know these.
- **Tactics:** redundancy (no single point of failure), replication, failover, health
  checks, load balancers, multi-AZ/region, graceful degradation, circuit breakers.
- **Tradeoff:** redundancy costs money; higher availability often means weaker consistency
  (CAP).
- **ClientLens:** async pipeline isolates failure — a down CRM/LLM doesn't take down meeting
  creation; circuit breaker + DLQ keep the system serving during a downstream outage.

### 3. Reliability / Fault Tolerance / Resilience
- **What:** operates correctly despite failures; recovers gracefully. (Reliability =
  correct over time; fault tolerance = keeps working when a component fails.)
- **Measure:** MTBF (mean time between failures), MTTR (mean time to recovery), error rate.
- **Tactics:** retries with backoff, idempotency, circuit breakers, DLQs, bulkheads,
  timeouts, replication, at-least-once delivery + idempotent consumers.
- **Tradeoff:** resilience machinery = complexity + eventual consistency.
- **ClientLens:** outbox (no lost events), `processed_events` idempotency, retry/backoff,
  circuit breaker, DLQ — the whole reliability toolkit.

### 4. Performance / Latency / Throughput
- **What:** **Latency** = time per request (how fast). **Throughput** = requests per unit
  time (how many). They're distinct — optimize the one that matters.
- **Measure:** use **percentiles, not averages** — p50, p95, **p99**, p999. Tail latency is
  what users feel. State targets ("p99 < 200ms").
- **Tactics:** caching, indexing, CDN, connection pooling, async/offload slow work, avoid
  N+1, denormalization, precomputation, batching.
- **Tradeoff:** caching → staleness; denormalization → write complexity; precompute → freshness.
- **ClientLens:** the bottleneck analysis — sync LLM (20s) on the request path exhausts the
  worker pool (Little's Law: 10/s × 20s = 200 concurrent); fix = 202 + move slow work to
  workers → API latency drops to milliseconds.

### 5. Consistency
- **What:** do all readers see the same, latest data?
- **Strong consistency** (reads see the latest write) vs **eventual consistency** (replicas
  converge over time). Also read-your-writes, monotonic reads, causal consistency.
- **Measure:** replication lag; staleness window.
- **Tactics:** strong → single leader / quorum / synchronous replication; eventual → async
  replication, accept lag.
- **Tradeoff:** **CAP** — under a network partition, choose consistency OR availability.
  Strong consistency costs latency/availability.
- **ClientLens:** meeting *creation* = strong (must not be lost); LLM analysis/status,
  search index, CRM sync = **eventual** (seconds behind is fine). This split *justifies* the
  async design.

### 6. Durability
- **What:** committed data survives crashes, restarts, hardware failure.
- **Measure:** data-loss probability; replication factor; RPO (recovery point objective — how
  much data you can lose).
- **Tactics:** write-ahead logs, replication (N copies), backups, fsync, durable queues.
- **Tradeoff:** durability (sync replication/fsync) costs write latency.
- **ClientLens:** MySQL is the durable source of truth; the outbox makes events durable before
  they're published (ACID durability).

### 7. Security
- **What:** protect confidentiality, integrity, availability of data and access.
- **Sub-areas:** **AuthN** (who are you) vs **AuthZ** (what can you do); encryption **in
  transit** (TLS) and **at rest**; input validation; secrets management; auditing; least
  privilege; rate limiting (also DoS defense).
- **Measure:** vulnerability count, audit coverage, time-to-patch.
- **Tactics:** JWT/OAuth, RBAC, parameterized queries (no injection), TLS, KMS/secrets vault,
  tenant isolation, audit logs.
- **Tradeoff:** security adds latency/complexity/friction.
- **ClientLens:** JWT (RS256, public-key verify in workers/MCP), tenant isolation baked into
  the repository, parameterized queries, MCP as an auth/audit boundary (never raw DB access).

### 8. Maintainability
- **What:** easy to change, extend, debug, and operate over time.
- **Measure:** cyclomatic complexity, coupling, test coverage, lead time for changes.
- **Tactics:** modularity, SOLID, clear abstractions/interfaces, tests, documentation, ADRs,
  IaC.
- **Tradeoff:** upfront abstraction cost vs long-term agility (don't over-engineer).
- **ClientLens:** provider abstractions (swap LLM/CRM by config), ADRs recording *why*,
  layered docs, ~46 tests.

### 9. Observability (Monitoring / Logging / Tracing / Metrics)
- **What:** understand system state from the outside; detect + diagnose issues.
- **Three pillars:** **metrics** (numbers over time — rates, latencies, saturation),
  **logs** (discrete events; structured), **traces** (one request across services).
- **Measure:** MTTD (time to detect), alert coverage, cardinality.
- **Tactics:** structured logging, correlation/trace IDs, dashboards, alerts on SLOs, RED
  (Rate/Errors/Duration) and USE (Utilization/Saturation/Errors) methods.
- **Tradeoff:** observability adds overhead/cost; too many alerts → fatigue.
- **ClientLens (planned Phase 7):** structured logs, metrics, Kafka lag monitoring, trace IDs
  to follow one request across the 3 workers (debuggability of the event-driven flow).

### 10. Cost / Efficiency
- **What:** resource and money efficiency at the required scale.
- **Measure:** cost per request/user; resource utilization.
- **Tactics:** right-sizing, autoscaling, spot instances, caching (fewer DB hits), efficient
  storage tiers, scaling the *specific* bottleneck not the whole system.
- **Tradeoff:** cost vs performance/redundancy.
- **ClientLens:** scaling workers (cheap, purpose-built) instead of the whole API avoids
  paying for a large fleet of blocked-waiting general-purpose servers.

---

## Second-tier NFRs (mention if relevant to the prompt)

- **Usability / Accessibility** — UX quality; WCAG compliance.
- **Portability** — runs across environments (containers, cloud-agnostic).
- **Interoperability** — plays well with other systems (standard protocols/formats).
- **Testability** — designed so it can be verified (DI, pure functions, injectable clock).
- **Deployability** — CI/CD, blue-green/canary, rollback, zero-downtime deploys.
- **Elasticity** — scales up *and back down* automatically with load.
- **Compliance / Regulatory** — GDPR, HIPAA, data residency, retention, right-to-be-forgotten.
- **Data privacy** — PII handling, minimization, anonymization.
- **Backup / Disaster Recovery** — RPO (data-loss tolerance) + RTO (recovery-time tolerance).
- **Localization / i18n** — languages, locales, time zones, currencies.
- **Extensibility** — add features without breaking existing ones (Open/Closed).
- **Concurrency** — correct behavior under simultaneous access (locks, idempotency,
  isolation).

---

## The fundamental tradeoffs (name these — they signal maturity)

- **CAP theorem:** under a network **P**artition, choose **C**onsistency or **A**vailability
  (you always tolerate partitions in a distributed system). CP vs AP systems.
- **PACELC:** extends CAP — *if* Partition then C-or-A, *Else* (normal operation) trade
  **L**atency vs **C**onsistency. More complete than CAP.
- **Consistency ↔ Latency/Availability:** strong consistency costs response time and
  availability.
- **Performance ↔ Cost:** faster usually costs more.
- **Availability ↔ Cost:** each extra "nine" is exponentially more expensive.
- **Space ↔ Time:** caching/denormalization trade memory/storage for speed.
- **Latency ↔ Throughput:** batching improves throughput but adds latency.
- **Security/Consistency ↔ Latency:** checks and coordination add time.
- **Simplicity ↔ Everything:** most resilience/scale features cost complexity — only add them
  when a requirement justifies it (don't introduce Kafka/sharding without a reason).

---

## Interview checklist — questions to ASK about NFRs

Rattle these off early to scope the problem:
- **Scale:** How many users? Requests/sec (average and **peak**)? Data volume? Growth rate?
- **Read/write ratio:** read-heavy or write-heavy? (Drives caching, replicas, sharding.)
- **Latency:** target p99? Real-time or can it be async?
- **Consistency:** must reads see the latest write, or is eventual OK? Which operations need
  strong vs eventual?
- **Availability:** target SLA (how many nines)? What's the cost of downtime?
- **Durability:** can we ever lose data? What's the acceptable RPO?
- **Security/compliance:** auth model? multi-tenant? PII? regulatory constraints (GDPR/HIPAA)?
- **Consistency of data across regions?** Geo-distribution needed?

## Back-of-envelope numbers worth memorizing
- Availability: 99.9% = ~8.76 h/yr · 99.99% = ~52 min/yr · 99.999% = ~5 min/yr.
- Latency ballpark: memory ns · SSD ~100µs · network round-trip within a DC ~0.5ms ·
  cross-region ~tens–hundreds of ms.
- Little's Law: **concurrency = arrival_rate × latency** (the ClientLens bottleneck math).
- Always reason about **peak**, not average, load.

---

## How NFRs shape ClientLens (one worked example to have ready)
Meeting pipeline chose **availability + eventual consistency** over strong consistency for
processing:
- Requirement: never *lose* a meeting (durability) but analysis can be seconds late
  (eventual consistency acceptable).
- Sync design failed on **performance** (Little's Law: 20s LLM × 10/s = 200 concurrent →
  worker-pool exhaustion → whole API, incl. login, down = **availability** failure).
- Fix served **scalability** (independent worker scaling), **availability** (failure
  isolation), **reliability** (outbox + idempotency + retry + DLQ + breaker).
- Cost paid: **consistency** became eventual, and **maintainability** took on the complexity
  of the async machinery.

That single narrative demonstrates you reason in NFRs and understand they trade off.
