# Interview Questions

The 35 mandatory system-design questions from SYSTEMDESING §31. As we build each feature,
we answer the relevant questions here (and/or link to the ADR that answers them).

The point (SYSTEMDESING §34) is the *reasoning*, not memorized "Kafka = good" answers:

```
Requirement → Problem → Possible solutions → Trade-off → Decision
           → Failure mode → Scaling strategy
```

Status: unanswered (to be filled in as the corresponding components are built).

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
