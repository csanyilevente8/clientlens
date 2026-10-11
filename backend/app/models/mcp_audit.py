"""Audit log for MCP tool calls (Phase 6, SYSTEMDESIGN §19/§772).

Every MCP tool invocation is recorded here — who called it, which tool, with what
arguments, for which tenant, and the outcome. Auditing is a DURABLE concern (§772): the row
is written in the SAME transaction as the tool's work (or, for auth failures, on its own),
so an audit record cannot be silently lost.

This is the "MCP requests are audited" Definition-of-Done item.
"""

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import IdentifiedTimestampedMixin


class McpAuditLog(Base, IdentifiedTimestampedMixin):
    __tablename__ = "mcp_audit_logs"

    # Who + where. tenant_id/user_id are null when the call failed authentication.
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    tool_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    arguments: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Outcome: "success" | "error" | "unauthorized".
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
