# System Design — Notification Service (worked example)

A system-design practice problem reasoned end-to-end (no implementation). Prompt:

> Frontend clients (mobile, browser) should be notified about upcoming meetings. The
> backend has three services, each with its own DB: a **Meeting service** (meeting outcomes
> come out as events), a **Client service** (user data), and a **Preference service** (per-
> user channel preference — web/mobile — and how long before the meeting to notify). Design
> a notification service that gathers these and sends notifications. (ClientLens is the
> context.)

Method (SYSTEMDESIGN §2): requirements → constraints → candidates → decision → tradeoffs →
failure modes → scaling.

---

## 1. Clarify requirements (ask these first — asking IS the senior signal)

Functional:
- Notify a user a configurable lead time before a meeting (e.g. "30 min before").
- Respect per-user channel preferences (web push, mobile push, maybe email/SMS).
- Respect opt-out.

Questions to pin down:
- **Scale?** users/meetings, notifications/sec at peak (decides cron-job vs heavy infra).
- **Lead-time granularity?** minutes? multiple lead times per user ("1 day" AND "30 min")?
- **Mutability?** can a meeting be rescheduled/cancelled after scheduling? (the hard part)
- **Delivery guarantee?** at-least-once (may duplicate) vs exactly-once-ish. A missed
  reminder is bad; a duplicate is survivable.
- **Timeliness tolerance?** within ~1 min acceptable, or to-the-second?

Assumptions for this write-up: moderate scale, configurable lead time, meetings CAN change,
at-least-once + dedup, ~1 min tolerance.

## 2. Constraints that shape the design

Defining constraint: a **time-based, future-scheduled action across three services that each
own their own data**. Two sub-problems:
1. **Data federation** — need data from all three services; no shared DB (DB-per-service).
2. **Scheduling** — fire at `meeting_time − lead_time`, which is in the future and may move.

## 3. Core question: how does the notification service get the data?

**(a) Synchronous fan-out** — query the 3 services via REST at notification time.
- Pro: always fresh, simple.
- Con: **temporal coupling** — if any service is down at send time, you fail; hammers the
  sources. Bad for a *scheduled* action.

**(b) Event-driven read model (RECOMMENDED).** Each service publishes events; the
notification service subscribes and keeps a **local denormalized copy** of only what it
needs:
- Meeting → `MeetingScheduled / MeetingRescheduled / MeetingCancelled`
- Client → `UserCreated / UserUpdated` (email, device tokens)
- Preference → `PreferencesUpdated` (channels, lead_time, opt_out)
Local table: `(user_id, meeting_id, meeting_time, notify_at, channels, contact_tokens,
lead_time, opted_out, status, version)`. At send time, everything is already local — no
cross-service calls on the hot path.
- Pro: **failure isolation** (sources can be down; delivery still works), no load on sources
  at send time, scales independently. Fits ClientLens (meeting service already emits events).
- Con: **eventual consistency** (read model lags), must handle **duplicate/out-of-order**
  events (idempotency).

**(c) Hybrid** — event-driven read model for the schedule + a *fresh* preference/contact
lookup at send time. Adds back some coupling; start with (b), add the lookup only if stale
preferences become a real problem.

**Decision: (b).** The trigger is a future scheduled action — decouple the send moment from
the health of source services and assemble data ahead of time.

## 4. The hard part: scheduling (meetings can move)

**(a) Poll a "due" table (RECOMMENDED to start).** Store `notify_at = meeting_time −
lead_time`; a worker polls every ~1 min: `WHERE notify_at <= now() AND status = PENDING`.
- Pro: simple, robust; **reschedule = just UPDATE the row**; mirrors the outbox publisher.
- Con: poll granularity = timing precision; needs an index on `notify_at`.

**(b) Delay queue / scheduled messages** (SQS delay, RabbitMQ TTL+DLX, scheduler).
- Pro: no polling, scales well.
- Con: **reschedule/cancel is painful** — can't easily edit/un-send an in-flight delayed
  message; delay limits vary. Would need a re-check at delivery.

**(c) Timer wheel / dedicated scheduler (Quartz-like).**
- Pro: precise, efficient at huge scale. Con: more infra; overkill until scale demands it.

**Decision: start with (a) polling**, because of the reschedule requirement (row UPDATE is
trivial vs editing a queued message). Evolve to a delay queue / scheduler later if precision
or scale demands — record it in an ADR. Don't add a scheduler before a requirement justifies
it.

## 5. Reschedules & cancellations (interviewers push here)

Because `notify_at` is derived from the meeting time:
- **Reschedule:** `MeetingRescheduled` → UPDATE the row → recompute `notify_at`. Trivial with
  the polling table (the reason a delay queue was avoided).
- **Cancel:** `MeetingCancelled` → set `status = CANCELLED` / delete → poller skips it.
- **Race:** reschedule arrives *after* we've sent → send a correction, or accept it
  (at-least-once world). State that you've considered it.
- **Out-of-order events:** apply an update only if it's **newer** than current state
  (version/event-time, last-writer-wins by event time, not arrival time).

## 6. Delivery, idempotency, failure modes

- **Idempotency:** unique key per notification `(meeting_id, notify_at, channel)`; at-least-
  once polling + worker crashes could retry a send → the sent-marker prevents duplicate
  delivery. (Same as `processed_events`.)
- **Channel = flaky external** (APNs/FCM/web push) → retries + backoff, circuit breaker, DLQ
  for permanent failures. (Same as the CRM worker.)
- **Failure modes:**
  - Notification service down → on restart the poller catches up (durable in DB, not memory);
    some fire late — acceptable within tolerance.
  - Source events lag → stale read model → hybrid fresh-lookup for critical fields, or accept
    the window.
  - Channel provider down → retry/breaker/DLQ; don't lose the notification.
  - Clock skew → derive timing from authoritative meeting time; consistent time source.

## 7. Scaling

- **Partition by user_id / meeting_id** so multiple pollers/workers process disjoint rows:
  Kafka partitions, or sharded polling with `SELECT ... FOR UPDATE SKIP LOCKED`.
- Read-model ingestion scales as independent consumers per source topic.
- Watch the due-table poll at scale → index `notify_at`, partition the table, or graduate to
  a delay queue / scheduler.

## 8. 60-second summary (how to open)

> "Event-driven consumer with its own read model: subscribe to meeting, user, and preference
> events; keep a local denormalized table so at send time it depends on no other service.
> For timing, store `notify_at = meeting_time − lead_time` and poll a due table (like a
> transactional outbox) — which makes reschedules trivial (just update the row), whereas a
> delay queue can't easily edit an in-flight message. Delivery goes through per-channel
> senders with retries, a circuit breaker, and a DLQ, and each send is idempotent (unique key
> on meeting+time+channel) because at-least-once + crashes mean duplicates. Main tradeoff is
> eventual consistency in the read model, acceptable because second-stale data is fine, and
> the decoupling buys failure isolation + independent scaling. If scale/precision demanded
> it, I'd evolve the poller into a dedicated scheduler and record it in an ADR."

---

## Architecture diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              EVENT SOURCES                                      │
│  ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────────────┐     │
│  │  Meeting Service  │   │  Client Service   │   │  Preference Service      │     │
│  │  (own DB)         │   │  (own DB)         │   │  (own DB)                │     │
│  │  meetings, times, │   │  users, emails,   │   │  channels (web/mobile),  │     │
│  │  participants     │   │  device tokens    │   │  lead times, opt-out     │     │
│  └────────┬─────────┘   └────────┬─────────┘   └────────────┬─────────────┘     │
│           │ emits                │ emits                     │ emits             │
│           ▼                      ▼                           ▼                   │
│  MeetingScheduled         UserCreated               PreferencesUpdated          │
│  MeetingRescheduled       UserUpdated               (channels, lead_time,       │
│  MeetingCancelled         (email, device tokens)     opt_out)                   │
└───────────┼──────────────────────┼───────────────────────────┼───────────────────┘
            ▼                      ▼                           ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           MESSAGE BROKER (Kafka)                                │
│   topic: meetings.lifecycle   topic: users.changes   topic: preferences.changes │
└─────────┬──────────────────────────┬───────────────────────────┬────────────────┘
          ▼                          ▼                           ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        NOTIFICATION SERVICE                                     │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │  Event Consumer Layer                                                     │  │
│  │  Subscribes to all 3 topics; builds + updates the local read model.       │  │
│  │  Handles out-of-order (apply if newer). Idempotent (event_id, consumer).  │  │
│  └─────────────────────────────────┬─────────────────────────────────────────┘  │
│                                    ▼ writes / updates                           │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │  Notification DB (read model) — scheduled_notifications                   │  │
│  │   id | user_id | meeting_id | meeting_time | notify_at | channels |       │  │
│  │   contact_tokens | lead_time | opted_out | status | version               │  │
│  │   notify_at = meeting_time − lead_time ; status: PENDING→SENT/CANCELLED    │  │
│  │   INDEX (notify_at, status)  ← poller hot path                            │  │
│  │   Rescheduled → UPDATE notify_at ; Cancelled → status=CANCELLED ;         │  │
│  │   PreferencesUpdated → UPDATE channels/lead_time/opted_out                │  │
│  └─────────────────────────────────┬─────────────────────────────────────────┘  │
│                                    ▼ polled by                                  │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │  Scheduler (Poller) — every ~1 min:                                       │  │
│  │   SELECT ... WHERE notify_at <= now() AND status='PENDING'                │  │
│  │   AND opted_out=false ORDER BY notify_at LIMIT n FOR UPDATE SKIP LOCKED    │  │
│  │   (same pattern as the outbox publisher)                                  │  │
│  └─────────────────────────────────┬─────────────────────────────────────────┘  │
│                                    ▼ dispatch per channel                       │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │  Channel Senders:  [Web Push] [Mobile Push APNs/FCM] [Email?]             │  │
│  │   each: retry+backoff · circuit breaker · DLQ · idempotent key            │  │
│  │   (meeting_id+notify_at+channel).  success → status=SENT ; perm fail → DLQ │  │
│  └─────────────────────────────────┬─────────────────────────────────────────┘  │
└────────────────────────────────────┼─────────────────────────────────────────────┘
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      CLIENTS:  [ Browser (Web Push) ]   [ Mobile App (APNs/FCM) ] │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### End-to-end flow (one notification)
1. Meeting Service creates a meeting → `MeetingScheduled {meeting_id, user_id, time}`.
2. Notification consumer receives it → reads local prefs (lead 30m, channel mobile) →
   writes `scheduled_notifications {notify_at = time−30m, status=PENDING}`.
3. At `notify_at`, the poller picks the row → dispatches to Mobile Push sender.
4. Sender calls FCM/APNs → success → `status=SENT`; failure → retry/backoff → DLQ if
   permanent.

**Reschedule:** `MeetingRescheduled` → UPDATE `notify_at` → old time never fires.
**Cancel:** `MeetingCancelled` → `status=CANCELLED` → poller skips.

---

## Reused ClientLens patterns (say this to show it's not hand-wavy)
- **Event consumer + read model** ← index-worker / CRM-worker consuming `IntelligenceExtracted`
  and maintaining their own stores.
- **Poller over `scheduled_notifications`** ← the outbox publisher (poll, process, mark).
- **Channel senders (retry + backoff + idempotency key)** ← `HTTPCRMClient`.
- **Circuit breaker + DLQ (transient vs permanent)** ← the CRM worker.
- **Idempotent delivery (unique constraint)** ← `processed_events`.

## Tradeoffs named (maturity signal)
- Chose **eventual consistency** (read model) for **failure isolation + independent scaling**.
- Chose **polling** over delay queue for **easy reschedule/cancel** at the cost of timing
  precision bounded by the poll interval.
- At-least-once delivery → **idempotency required** (duplicates possible).
- Don't add a dedicated scheduler until scale/precision justifies it (avoid premature
  complexity).
