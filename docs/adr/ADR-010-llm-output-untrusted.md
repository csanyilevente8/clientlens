# ADR-010 — LLM output is untrusted: abstraction, validation, provenance

Status: Accepted (2026-09-28)

## Decision

Access all LLM analysis through an `LLMProvider` abstraction (Mock default, real providers
selectable by config). Treat LLM output as **probabilistic/untrusted**: parse it into a
Pydantic `MeetingAnalysis` schema, validate, and only then persist. On invalid output the
meeting goes to `FAILED` and no partial "trusted" intelligence is stored. Persist provenance
(model, model_version, prompt_version, processing_timestamp) with every analysis.

## Context

ClientLens turns meeting transcripts into structured intelligence (topics, goals, concerns,
action items, life events) via an LLM. LLMs are non-deterministic and can return malformed
or wrong output. Business logic must not couple to a vendor SDK (SPEC §14, Rule 3), and must
not trust raw model output (Rule 4). Tests must not depend on live LLM calls (SPEC §41).

## Requirements

- Provider-agnostic business logic; swap Mock/OpenAI/Anthropic by config (SPEC §46).
- Validate structured output before persistence (SPEC §15).
- Never persist invalid AI output as trusted data (Rule 4); failures -> status FAILED.
- Record how each analysis was produced (SPEC §16).
- Preserve provenance: each extracted item traces to its source meeting (SPEC §17).
- Deterministic tests (SPEC §41).

## Options

- **Call an LLM SDK directly in the endpoint/service** — couples business logic to a vendor,
  untestable without live calls. Rejected (Rule 3, §41).
- **LLMProvider protocol + config selection + MockLLMProvider default** (chosen).
- **Trust LLM JSON as-is** — rejected; a malformed/hallucinated response would corrupt data.
- **Pydantic-validate the output before persisting** (chosen).

## Why

The abstraction keeps the app provider-agnostic and testable (deterministic Mock). Pydantic
validation makes "untrusted output" concrete: output that doesn't fit the schema can't be
persisted. Provenance columns let us later reason about / re-run / audit analyses.

## Trade-offs

- Mock output is keyword-based, not "real" understanding — fine for pipeline/dev/tests, but
  not a quality signal for the real model.
- Storing each meeting's extraction as its own rows (no overwrite) can produce duplicate-ish
  facts across meetings; aggregating "current" goals is a read-time concern (deferred).
- Validation rejects borderline-but-useful output; we accept FAILED over corrupt data.

## Failure modes

- **LLM returns invalid/unparseable output:** ValidationError -> status FAILED, no
  intelligence persisted. The meeting is preserved; it can be reprocessed.
- **LLM returns plausible-but-wrong content:** schema-valid, so it persists — mitigated by
  provenance (we know model/prompt) and, later, human review / confidence (SPEC §16).
- **Provider misconfigured:** factory raises on unknown LLM_PROVIDER (fail fast at startup).

## Consequences

- New Pydantic `MeetingAnalysis` schema is the output contract.
- Five intelligence tables (topics/goals/concerns/action_items/life_events), each carrying
  tenant_id (isolation) + meeting_id + client_id (provenance).
- Meeting gains summary + provenance columns.
- Analysis currently runs SYNCHRONOUSLY in-request (Stage 1); Phase 3 moves it to a worker.
  The abstraction + validation are unchanged by that move.

## When we would reconsider this decision

- If we need streaming output or tool-calling, the single analyze_meeting() call may need a
  richer interface.
- If validation is too strict and drops useful output, add a lenient/repair step before
  rejecting.
- If real-time role/consistency needs change, revisit synchronous vs async placement
  (already planned for Phase 3).
