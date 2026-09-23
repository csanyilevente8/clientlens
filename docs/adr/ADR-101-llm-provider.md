# ADR 0002 — LLM provider: Anthropic (Claude), Mock default for dev/test

Status: Accepted (2026-09-22)

## Context

The spec requires an `LLMProvider` abstraction with MOCK plus one real provider, selectable
by configuration (§14, §46). AI tests must not depend on live LLM calls (§41).

## Decision

- **MOCK** is the default provider for local development and all deterministic tests.
- **Anthropic (Claude)** is the single real provider implemented initially.
- Provider is selected via configuration (`LLM_PROVIDER`), and business logic depends only
  on the `LLMProvider` interface — never on a specific SDK.

## Alternatives considered

- **OpenAI** — ubiquitous SDK, fine technically, but fits the project narrative less well.
- **Both real providers up front** — unnecessary scope; the abstraction makes adding OpenAI
  later trivial.

## Consequences

- The headline scenario ("ask Claude through MCP") and MCP (Anthropic-originated) form a
  coherent end-to-end story.
- OpenAI can be added later behind the same interface with no business-logic changes.
- Deterministic AI tests run entirely on the Mock provider.
