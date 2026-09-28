"""In-memory store for the mock CRM.

A real CRM is an opaque external datastore; we don't model it in MySQL. State lives
in process memory and resets on restart — which is fine (and realistic for a stub):
tests seed what they need, and the store's job is only to prove idempotency and let
us inspect what got synced.

Idempotency contract: the (future) CRM sync worker sends an Idempotency-Key with each
write. If the CRM has already seen that key, it returns the *same* resource instead of
creating a duplicate task. This is what makes at-least-once delivery safe end to end
(SYSTEMDESING §13).
"""

from __future__ import annotations

import threading
import uuid

from app.mock_crm.schemas import ActionItemResource, ActionItemSyncRequest
from app.utils.time import utcnow


class CRMStore:
    def __init__(self) -> None:
        # Guard the dicts: uvicorn may serve requests from a threadpool, and the store
        # is a shared singleton. A simple lock keeps create-or-return atomic.
        self._lock = threading.Lock()
        self._by_id: dict[str, ActionItemResource] = {}
        self._by_idempotency_key: dict[str, str] = {}

    def upsert_action_item(
        self, idempotency_key: str, req: ActionItemSyncRequest
    ) -> tuple[ActionItemResource, bool]:
        """Create the action item, or return the existing one for a seen key.

        Returns (resource, created) where `created` is False on an idempotent replay.
        """
        with self._lock:
            existing_id = self._by_idempotency_key.get(idempotency_key)
            if existing_id is not None:
                return self._by_id[existing_id], False

            crm_id = f"crm_{uuid.uuid4().hex[:12]}"
            resource = ActionItemResource(
                crm_id=crm_id,
                client_ref=req.client_ref,
                description=req.description,
                owner=req.owner,
                due_date=req.due_date,
                created_at=utcnow(),
            )
            self._by_id[crm_id] = resource
            self._by_idempotency_key[idempotency_key] = crm_id
            return resource, True

    def list_action_items(self) -> list[ActionItemResource]:
        with self._lock:
            return list(self._by_id.values())

    def get(self, crm_id: str) -> ActionItemResource | None:
        with self._lock:
            return self._by_id.get(crm_id)

    def clear(self) -> None:
        with self._lock:
            self._by_id.clear()
            self._by_idempotency_key.clear()
