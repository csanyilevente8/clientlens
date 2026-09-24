from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import IdentifiedTimestampedMixin


class Tenant(Base, IdentifiedTimestampedMixin):
    __tablename__ = "tenants"
    # a required string column, max length 255
    name: Mapped[str] = mapped_column(String(255), nullable=False)