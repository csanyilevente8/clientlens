"""Helpers for writing outbox events (SYSTEMDESING §10, §12).

add_outbox_event() stages an OutboxEvent on the given session but does NOT commit — the
caller commits it in the SAME transaction as the business change, which is the whole point
of the pattern (atomic business-write + event).
"""

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outbox import OutboxEvent

# Event type constants (the "event_type" in the SPEC §12 envelope).
MEETING_CREATED = "MeetingCreated"
INTELLIGENCE_EXTRACTED = "IntelligenceExtracted"


def add_outbox_event(
    session: AsyncSession,
    *,
    event_type: str,
    aggregate_id: str,
    tenant_id: str,
    payload: dict[str, Any],
) -> OutboxEvent:
    """Stage an outbox event on the session (caller commits it with the business change)."""
    event = OutboxEvent(
        event_type=event_type,
        aggregate_id=aggregate_id,
        tenant_id=tenant_id,
        payload=json.dumps(payload),
    )
    session.add(event)
    return event
