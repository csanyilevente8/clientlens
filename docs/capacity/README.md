# Capacity Estimation — Meeting Ingestion

Back-of-the-envelope math (SYSTEMDESING §4), reasoned before making scaling decisions.

## Baseline assumptions

```
10,000 tenants
100 clients / tenant
20 meetings / client / year
5 KB  metadata  / meeting
2 MB  transcript / meeting
```

## Volume

```
Meetings/year = 10,000 × 100 × 20 = 20,000,000  (20M)
Seconds/year  ≈ 31,500,000
Average rate  = 20M / 31.5M ≈ 0.63 meetings/second
```

## Why the average is misleading — peak is what matters

0.63/s assumes meetings arrive uniformly across every second of the year (incl. 3am,
weekends, holidays). Financial advisors work business hours, weekdays, a few time zones.
Concentrating 20M meetings into ~1/4 of the calendar gives a busy-hours rate of ~2.5/s;
adding burstiness (meetings cluster on the hour, after lunch) pushes the **peak to
~8-10 meetings/second**.

**Capacity must be sized for peak, not average.** If arrival rate exceeds processing
rate, work queues faster than it drains and the backlog grows without bound — the system
degrades or collapses precisely when it is busiest. Averages hide the spikes that kill you.

```
Average: ~0.63/s   (do NOT size for this)
Peak:    ~8-10/s    (size for this)
```

## Storage growth

```
Transcript storage/year = 20M × 2 MB = 40,000,000 MB = 40 TB / year
Metadata storage/year   = 20M × 5 KB = 100 GB / year
```

Transcripts grow **40 TB every year**. This does not belong in MySQL rows.

### Transcripts belong in object storage, not MySQL

MySQL is for structured, queryable, relational data (filter, join, index, transact).
A transcript is fetched by id (key → blob), never queried with `WHERE transcript LIKE`.
Keeping 40 TB of `TEXT` in MySQL rows would:

- bloat backups/restores (dragging 40 TB of text nobody queries),
- pollute the buffer pool (giant blobs evict hot rows from RAM → slow queries),
- inflate replication (every replica copies all the text),
- cost far more per GB than object storage.

**Pattern:** store the transcript in object storage (e.g. S3); keep only a pointer
(`s3_key`) + the ~5 KB of structured metadata in the MySQL row. (Ties to ADR-004:
"MySQL as source of truth for *structured* data" — big blobs are not structured data.)

### Known limitation (current code)

The current `Meeting` model stores `transcript` as a MySQL `TEXT` column — i.e. the naive
design argued against above. Acceptable for early phases with small demo data; a future
ADR/refactor should move transcripts to object storage. (Good interview point: "I know
this doesn't scale; here's what I'd change and why.")

## Summary

```
Meetings:     20M/year
Average:      0.63/s   (misleading — hides spikes)
Peak:         ~8-10/s  (size for this)
Metadata:     ~100 GB/year  → MySQL
Transcripts:  40 TB/year    → object storage (currently TEXT in MySQL: known debt)
```
