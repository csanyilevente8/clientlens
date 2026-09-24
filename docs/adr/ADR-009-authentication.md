# ADR-009 — Authentication (JWT, RS256, role in token, login by slug+email)

Status: Accepted (2026-09-24)

## Decision

Stateless JWT authentication. Tokens are signed with **RS256** (RSA key pair). The token
carries `sub` (user id), `tenant_id`, and `role` as claims. Users log in with
**tenant slug + email + password**. Short-lived access tokens only (no refresh token yet).

## Context

ClientLens is multi-tenant (ADR-008). Every request must resolve to a user, their tenant,
and their role, enforced server-side (SYSTEMDESING §16: JWT → user → tenant → authorization
→ query). Emails are unique *per tenant* (not global), so email alone cannot identify a
user. Multiple services (API, workers, MCP server) will eventually need to verify tokens.

## Requirements

- Authenticate a user and issue a credential the API trusts on later requests.
- Resolve tenant + role server-side; never trust a client-supplied `tenant_id` (§16).
- Support RBAC roles ADMIN / ADVISOR / READ_ONLY (SPEC §9).
- Short-lived access tokens (SPEC §9).
- Other services must be able to verify tokens without holding the signing secret.

## Options

**Token format**
1. Server-side sessions (stateful, store in DB/Redis) — needs shared session store, extra
   infra; rejected (SYSTEMDESING §2: no infra without a requirement).
2. Stateless JWT (chosen) — no session store; claims travel in the token.

**Signing algorithm**
1. HS256 (shared secret) — simplest, but every verifying service needs the secret, which
   is also the signing secret. Weakens the "workers/MCP verify" story.
2. RS256 (chosen) — private key signs, public key verifies; verifiers never hold the
   signing key. Slightly more setup (key pair, key management).

**Role freshness**
1. Role in token (chosen) — stateless, no per-request lookup; stale until token expires.
2. Look up role per request — always fresh, but a DB read on every call.

**Login identity**
1. Global unique email — email alone identifies user, but conflicts with ADR-008's
   per-tenant email uniqueness.
2. tenant slug + email + password (chosen) — matches per-tenant email; slug is a
   human-friendly public tenant identifier (unique column on Tenant).

## Why

Stateless JWT avoids a session store (no requirement for one yet). RS256 fits the coming
multi-service topology: workers and the MCP server verify with the public key only.
Role-in-token is an acceptable staleness trade-off because roles change rarely (and tokens
are short-lived, so staleness is bounded). Login by slug+email is forced by the per-tenant
email decision and gives usable UX.

## Trade-offs

- **Stateless JWT:** cannot revoke a token before expiry (no server-side session to kill).
  Mitigated by short lifetimes; a denylist can be added if revocation becomes a requirement.
- **Role in token:** a role change (e.g. demotion) is not effective until the token
  expires. Acceptable given short expiry.
- **RS256:** key-pair management (generation, storage, rotation) is more work than a shared
  secret.

## Failure modes

- **Missing/invalid/expired token:** request rejected with 401 (fail closed). Tenant is
  never inferred from anything but a verified token.
- **Client sends tenant_id in body/header:** ignored — tenant comes only from the verified
  token's claim (§16).
- **Private key leaked:** attacker can mint tokens; rotate keys, all old tokens invalid on
  key change. (Why prod keys must be secret-managed and rotatable — §26/§34.)
- **Clock skew:** exp/iat validation can misfire; keep servers time-synced.

## Consequences

- Tenant model gains a unique `slug` column (login identifier).
- A "current user" dependency decodes the token on every protected request and yields
  (user_id, tenant_id, role); this is the single server-side resolution point.
- RBAC is enforced from the `role` claim.
- The tenant-scoped repository (ADR-008, Approach B) consumes the resolved tenant_id.

## When we would reconsider this decision

- If token revocation becomes a hard requirement → add refresh tokens + a denylist, or move
  to server-side sessions.
- If role changes must take effect immediately → look up role per request instead of
  embedding it.
- If we never add a second verifying service → HS256 would have been simpler (but RS256
  costs little now).
