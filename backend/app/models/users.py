from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import IdentifiedTimestampedMixin
from app.models.roles import Role


class User(Base, IdentifiedTimestampedMixin):
    __tablename__ = "users"

    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), index=True)
    email: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )
