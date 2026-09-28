"""CRM client abstraction (SPEC §14, §46; Rule 3).

Business logic (the future CRM sync worker) depends on the CRMClient protocol, never on
httpx or a specific CRM SDK. This is the same abstraction pattern as LLMProvider.

Error taxonomy — this is the important part for retry logic:
    CRMUnavailable  -> TRANSIENT (503, timeout, connection error). Safe to retry.
    CRMBadRequest   -> PERMANENT (4xx). Retrying will never succeed; the caller (worker)
                       should dead-letter instead of retrying.

Separating transient from permanent failures is what lets each layer make the right
call: the HTTP client retries transient blips; the worker dead-letters permanent ones.
"""

from typing import Protocol

from pydantic import BaseModel, Field


class ActionItemSync(BaseModel):
    """One action item to push into the CRM. Mirrors the mock CRM's request shape."""

    client_ref: str = Field(..., min_length=1, max_length=64)
    description: str = Field(..., min_length=1, max_length=1000)
    owner: str | None = Field(default=None, max_length=255)
    due_date: str | None = Field(default=None, max_length=32)


class SyncResult(BaseModel):
    crm_id: str
    created: bool  # False on an idempotent replay (the CRM had already seen the key)


class CRMError(Exception):
    """Base class for CRM client failures."""


class CRMUnavailable(CRMError):
    """Transient failure (503 / timeout / connection error). Safe to retry."""


class CRMBadRequest(CRMError):
    """Permanent failure (4xx). Retrying will not help — dead-letter instead."""


class CRMClient(Protocol):
    async def sync_action_item(self, idempotency_key: str, item: ActionItemSync) -> SyncResult:
        """Push one action item, keyed for idempotency.

        Must raise CRMUnavailable on transient failure (so callers can retry) and
        CRMBadRequest on permanent failure (so callers can dead-letter).
        """
        ...
