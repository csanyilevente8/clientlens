"""HTTP CRM client with bounded retries + exponential backoff.

This layer handles *transient* failures — a single 503, a timeout, a dropped
connection — by retrying a few times with exponential backoff and jitter. It does NOT
try to survive a sustained outage; that's the worker layer's job (redelivery, circuit
breaker, DLQ). Keeping the two concerns separate keeps each simple:

    HTTP client  : "this one call blipped, try again a few times"   (this file)
    CRM worker   : "the CRM has been down for a while, back off,     (later, mentor-mode)
                    trip the breaker, and dead-letter poison messages"

Retry policy:
    - Retry on CRMUnavailable (503 / timeout / connection error) up to `max_attempts`.
    - Do NOT retry on 4xx (CRMBadRequest) — permanent, retrying can't help.
    - Backoff = min(base * 2**(attempt-1), cap), multiplied by random jitter in [0.5, 1.0)
      to avoid thundering-herd retries when the CRM recovers.

Idempotency-Key is sent on every attempt (same key across retries) so a retry after an
ambiguous failure never creates a duplicate task in the CRM.
"""

from __future__ import annotations

import asyncio
import random
from typing import Self

import httpx

from app.integrations.crm.base import (
    ActionItemSync,
    CRMBadRequest,
    CRMUnavailable,
    SyncResult,
)


def backoff_delay(attempt: int, *, base: float = 0.5, cap: float = 8.0) -> float:
    """Exponential backoff with full jitter, capped. attempt is 1-based."""
    ceiling = min(base * (2 ** (attempt - 1)), cap)
    return ceiling * (0.5 + random.random() * 0.5)


class HTTPCRMClient:
    """CRMClient backed by httpx against the (mock or real) CRM HTTP API."""

    def __init__(
        self,
        base_url: str,
        *,
        max_attempts: int = 3,
        timeout: float = 5.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._max_attempts = max_attempts
        self._timeout = timeout
        # Allow injecting a client (tests use httpx's ASGITransport to hit the mock CRM
        # app in-process — no network, no sleeps needed for the happy path).
        self._client = client
        self._owns_client = client is None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout)
        return self._client

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def sync_action_item(self, idempotency_key: str, item: ActionItemSync) -> SyncResult:
        client = await self._get_client()
        last_exc: CRMUnavailable | None = None

        for attempt in range(1, self._max_attempts + 1):
            try:
                resp = await client.post(
                    "/crm/action-items",
                    json=item.model_dump(),
                    headers={"Idempotency-Key": idempotency_key},
                )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                # Network-level transient failure -> retryable.
                last_exc = CRMUnavailable(f"CRM transport error: {exc}")
            else:
                if resp.status_code in (200, 201):
                    body = resp.json()
                    return SyncResult(crm_id=body["crm_id"], created=resp.status_code == 201)
                if 400 <= resp.status_code < 500:
                    # Permanent: bad payload / missing key. Retrying cannot help.
                    raise CRMBadRequest(f"CRM rejected request ({resp.status_code}): {resp.text}")
                # 5xx -> transient, retryable.
                last_exc = CRMUnavailable(f"CRM returned {resp.status_code}")

            if attempt < self._max_attempts:
                await asyncio.sleep(backoff_delay(attempt))

        # Exhausted retries on a transient failure. Raise so the caller (worker) can
        # decide to requeue / trip its circuit breaker / dead-letter.
        raise last_exc or CRMUnavailable("CRM unavailable after retries")
