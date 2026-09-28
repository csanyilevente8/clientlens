"""Extracted client intelligence, persisted per meeting with provenance (SPEC §16, §17).

Each row traces back to the meeting that produced it (meeting_id) and denormalizes
tenant_id (for the tenant-scoped repository) and client_id (to query a client's goals/
concerns without joining through meetings). History is not overwritten — each meeting's
extraction is its own set of rows.
"""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import IdentifiedTimestampedMixin


class _IntelligenceBase(IdentifiedTimestampedMixin):
    """Shared provenance columns for all intelligence rows."""

    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), index=True)
    meeting_id: Mapped[str] = mapped_column(String(36), ForeignKey("meetings.id"), index=True)
    client_id: Mapped[str] = mapped_column(String(36), ForeignKey("clients.id"), index=True)


class MeetingTopic(Base, _IntelligenceBase):
    __tablename__ = "meeting_topics"
    topic: Mapped[str] = mapped_column(String(255), nullable=False)


class ClientGoal(Base, _IntelligenceBase):
    __tablename__ = "client_goals"
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    timeframe: Mapped[str | None] = mapped_column(String(255), nullable=True)


class ClientConcern(Base, _IntelligenceBase):
    __tablename__ = "client_concerns"
    description: Mapped[str] = mapped_column(String(1000), nullable=False)


class ActionItem(Base, _IntelligenceBase):
    __tablename__ = "action_items"
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    owner: Mapped[str | None] = mapped_column(String(255), nullable=True)


class LifeEvent(Base, _IntelligenceBase):
    __tablename__ = "life_events"
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
