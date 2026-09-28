from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.meeting_status import MeetingStatus
from app.models.mixins import IdentifiedTimestampedMixin


class Meeting(Base, IdentifiedTimestampedMixin):
    __tablename__ = "meetings"

    # Tenant-owned (ADR-008): carries tenant_id directly so the tenant-scoped repository
    # can filter without joining through client. Denormalized for uniform isolation.
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), index=True)

    # Which client this meeting is about.
    client_id: Mapped[str] = mapped_column(String(36), ForeignKey("clients.id"), index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Transcripts are large (SPEC ~2MB) -> TEXT, not a bounded VARCHAR.
    transcript: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[MeetingStatus] = mapped_column(
        Enum(MeetingStatus), nullable=False, default=MeetingStatus.CREATED
    )

    # Filled in after analysis. Nullable until processing completes.
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Provenance: how the analysis was produced (SPEC §16 — LLM output is probabilistic).
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    processing_timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
