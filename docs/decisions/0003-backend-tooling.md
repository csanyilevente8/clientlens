# ADR 0003 — Backend tooling: uv

Status: Accepted (2026-09-22)

## Context

The spec requires `pyproject.toml` (§5) but does not name a package/environment manager.
Reproducible builds with a real lockfile are desirable (the developer comes from a
Maven/Gradle background).

## Decision

Use **uv** for dependency management, virtual environments, and lockfiles. Retain a
standard `pyproject.toml`. Commit `uv.lock` for reproducibility.

## Alternatives considered

- **poetry** — mature with a good lockfile, but slower and heavier.
- **pip + requirements.txt** — simplest, but no true lockfile; weaker reproducibility than
  the developer's existing Java tooling.

## Consequences

- Fast, reproducible installs; single tool for venv + resolution + locking.
- `uv.lock` is committed and must be kept in sync with `pyproject.toml`.
