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
