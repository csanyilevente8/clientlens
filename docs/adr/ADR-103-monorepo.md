# ADR 0004 — Monorepo

Status: Accepted (2026-09-22)

## Context

The system comprises backend, multiple workers, an MCP server, a frontend, and
infrastructure (Docker, Helm, Terraform). We had to choose a single repository or multiple
repositories (e.g., separate backend/frontend/infra repos).

## Decision

Use a single **monorepo** (`clientlens/`) following the SPEC §51 layout. Services remain
independently deployable (separate containers and Helm deployments) — repo layout and
deployment topology are orthogonal.

## Alternatives considered

- **Multi-repo (be/fe/k8s separate)** — enables independent deploy cadence and access
  control, but adds cross-repo coordination for the common case of changes that touch API
  schema + TS types + infra together, and complicates the mandated `docker compose up`
  (§36) local dev.

## Consequences

- Cross-cutting changes (API schema → TS types → ConfigMap) are atomic: one commit/PR.
- One `docker-compose.yml`, one `docs/` tree, one `PROGRESS.md` — simpler continuity.
- CI must use path filters so unrelated changes don't rebuild everything.
- Service boundaries (§44 Rule 1) are enforced by module/directory structure, not repo
  separation. Monorepo ≠ monolith: services still deploy and scale independently.
