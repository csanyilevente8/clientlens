# Capacity Estimation

Back-of-the-envelope calculations (SYSTEMDESING §4) done *before* scaling decisions.

Baseline assumptions to reason from:

```
10,000 tenants
100 clients / tenant
20 meetings / client / year
5 KB metadata / meeting
2 MB transcript / meeting
```

For each estimate, derive: total meetings, daily ingestion, avg & peak req/s, DB storage,
transcript storage, Kafka event volume, embedding volume. Then identify average load, peak
load, storage growth, read/write ratio, hot paths, expensive operations.

_To be filled in before Stage 2 (identifying the bottleneck) and the scaling exercises._
