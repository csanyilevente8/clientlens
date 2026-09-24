from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import IdentifiedTimestampedMixin


class Client(Base, IdentifiedTimestampedMixin):
    __tablename__ = "clients"

    # Tenant ownership: every tenant-owned entity carries tenant_id (ADR-008, SPEC §7).
    # Indexed because every query filters by tenant (SYSTEMDESING §15).
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), index=True)

    # The advisor's client (the person being advised). Free-text display name.
    name: Mapped[str] = mapped_column(String(255), nullable=False)
