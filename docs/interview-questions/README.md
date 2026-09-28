# Interview Questions

The 35 mandatory system-design questions from SYSTEMDESING §31. As we build each feature,
we answer the relevant questions here (and/or link to the ADR that answers them).

The point (SYSTEMDESING §34) is the *reasoning*, not memorized "Kafka = good" answers:

```
Requirement → Problem → Possible solutions → Trade-off → Decision
           → Failure mode → Scaling strategy
```

Status: in progress — answers added as the corresponding analysis is done.

### Answered so far (bottleneck analysis, capacity/failure docs)

**Q1 — Why Kafka instead of synchronous HTTP?**
Synchronous processing holds a worker/connection for the full ~20s LLM call. At peak ~10/s,
Little's Law gives ~200 concurrent in-flight → exhausts the worker pool (blocked, not CPU) →
whole API (incl. login) becomes unresponsive. Async (202 + queue + workers) frees the API
worker in milliseconds and lets workers scale independently. See
`capacity/bottleneck-synchronous-processing.md`.

**Q7 — What happens if the worker crashes?**
The "work owed" fact lives durably in the queue, not process memory. Worker acks only on
success; a crash before ack → queue redelivers to another worker → the meeting still gets
processed. Nothing lost.

**Q8 — Can the same event be processed twice?**
Yes. At-least-once delivery + redelivery means a worker can finish + save then crash before
acking → the event is redelivered and processed again. Hence consumers must be idempotent.

**Q14 — What happens if the LLM is down?**
Async: meeting is persisted + enqueued before any LLM call, so ingestion succeeds (202);
events wait/retry in the queue; workers drain the backlog when the LLM recovers. Nothing
lost. (Synchronous: the request 5xx's and can roll back, losing the meeting.)

**Q21 vs Q22 — How would you scale the API vs the AI workers?**
Different scaling dimensions. API scales with request traffic; workers scale with processing
backlog (queue lag). Slow LLM work should not force the whole API to scale — move it off the
request path and scale the worker pool independently.

**Q34/Q35 — Which operations need strong vs eventual consistency?**
Meeting ingestion (create) = strong (must not be lost). LLM analysis / status = eventual
(acceptable to be seconds/minutes behind). This split is exactly what justifies async.

---

Remaining questions to answer as later phases are built:

1. Why Kafka instead of synchronous HTTP?
2. Why Kafka instead of RabbitMQ?
3. Why MySQL instead of MongoDB?
4. Why do we need a vector database?
5. Why not store embeddings in MySQL?
6. What happens if Kafka is unavailable?
7. What happens if the worker crashes?
8. Can the same event be processed twice?
9. How do you make the consumer idempotent?
10. Why do we need an outbox?
11. What happens if the outbox publisher crashes?
12. How do you handle retries?
13. What happens to poison messages?
14. What happens if the LLM is down?
15. What happens if the CRM is down?
16. Where is the source of truth?
17. Which data is eventually consistent?
18. Where would you add caching?
19. What would you cache?
20. How would you invalidate it?
21. How would you scale the API?
22. How would you scale AI workers?
23. What determines the number of Kafka partitions?
24. How would you handle 10x traffic?
25. How would you handle 100x traffic?
26. Where is the bottleneck?
27. How would you detect the bottleneck?
28. How would you monitor Kafka lag?
29. How would you debug one request across multiple services?
30. How do you guarantee tenant isolation?
31. Why shouldn't MCP access the DB directly?
32. What happens if vector search is unavailable?
33. What happens if MySQL is unavailable?
34. Which operations require strong consistency?
35. Which operations can be eventually consistent?
