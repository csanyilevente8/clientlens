"""Idempotency guard for event consumers (SYSTEMDESING §9, §13).

A row here means "this consumer has already processed this event". The UNIQUE constraint on
(event_id, consumer_name) is the correctness guarantee against concurrent duplicates; the
application-level check is an optimization for the common case. The row must be inserted in
the SAME transaction as the work it guards, so "marked processed" and "work done" are always
consistent.
"""

from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import IdentifiedTimestampedMixin
from app.utils.time import utcnow


class ProcessedEvent(Base, IdentifiedTimestampedMixin):
    __tablename__ = "processed_events"

    event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    consumer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    __table_args__ = (
        UniqueConstraint("event_id", "consumer_name", name="uq_processed_events_event_consumer"),
    )
