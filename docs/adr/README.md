# Architecture Decision Records (ADRs)

Per `SYSTEMDESING.md` §27, every significant architecture decision gets an ADR here.
Writing ADRs *is* the system-design practice — each one is a written answer to the kind
of question asked in a system-design interview (SYSTEMDESING §31).

## Template (SYSTEMDESING §27)

Every ADR must contain these sections:

```
# Decision
# Context
# Requirements
# Options
# Why
# Trade-offs
# Failure modes
# Consequences
# When we would reconsider this decision
```

The last section ("when we would reconsider") is required — no decision is permanent;
name the conditions that would flip it.

## Numbering scheme

- **ADR-001 … ADR-0xx** — core system-design decisions (reserved slots from §27):
  - ADR-001 kafka-for-async-processing *(pending)*
  - ADR-002 transactional-outbox *(pending)*
  - ADR-003 idempotent-consumers *(pending)*
  - ADR-004 mysql-as-source-of-truth + vector store ✅
  - ADR-005 vector-search *(may merge with 004)*
  - ADR-006 mcp-application-boundary *(pending)*
  - ADR-007 cache-strategy *(pending)*
  - ADR-008+ multi-tenancy, auth, etc. *(as we build them)*
- **ADR-1xx** — project-setup decisions (not core system design): LLM provider (101),
  backend tooling (102), monorepo (103). These predate the §27 template and use a lighter
  format; they will be expanded to the full template only if a decision proves contentious.

## Why decisions must precede code

The working method (SYSTEMDESING §2):

```
Requirement → Constraint → Candidate solutions → Decision → Trade-off
           → Failure mode → Scaling consequence
```

Do not introduce distributed-systems complexity (Kafka, Redis, extra services) without a
concrete requirement. Ask "why do we need this component?" before "what technology?".
