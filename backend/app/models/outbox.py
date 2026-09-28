"""Transactional outbox (SYSTEMDESING §10).

An outbox row is written in the SAME DB transaction as the business change, so the
"intent to publish an event" is durable atomically with the data. A separate publisher
(Slice 2) drains unpublished rows to Kafka. This avoids the dual-write problem (DB commits
but Kafka publish fails -> lost event).

The row's `id` doubles as the event_id used later for idempotent consumption (§13).
"""

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import IdentifiedTimestampedMixin


class OutboxEvent(Base, IdentifiedTimestampedMixin):
    __tablename__ = "outbox_events"

    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # JSON body of the event (thin: references, not the full aggregate).
    payload: Mapped[str] = mapped_column(Text, nullable=False)

    # NULL until the publisher has sent it to Kafka. The publisher polls for NULLs.
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, index=True
    )
