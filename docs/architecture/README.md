# Architecture Diagrams

Diagrams for the system (SYSTEMDESING §32). Target set:

```
01-current-architecture
02-meeting-ingestion
03-kafka-flow
04-outbox-pattern
05-idempotency
06-failure-handling
07-mcp-rag-flow
08-kubernetes-architecture
09-scaling
```

Plus sequence diagrams for important flows (e.g. meeting ingestion → outbox → Kafka → AI
worker → LLM → MySQL → Vector DB).

_To be added as each architecture stage is reached. Text/Mermaid diagrams are fine; PNGs
optional._

## Written analyses

- `event-driven-vs-direct-call.md` — why the meeting pipeline is event-driven (outbox →
  Kafka → 3 consumers) vs direct synchronous calls; what it bought (failure isolation,
  independent scaling, loose coupling) and what it cost (eventual consistency + outbox/
  idempotency/DLQ/breaker machinery). Complements diagram `03-kafka-flow`.
