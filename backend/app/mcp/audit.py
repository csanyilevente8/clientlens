"""Audit recording for MCP tool calls.

Each tool call writes one durable audit row (SYSTEMDESIGN §772). We record in a dedicated,
short-lived session and commit immediately — the audit trail must survive even if the tool's
own work later fails, so it does not share the tool's transaction.

Sensitive values should not be logged verbatim; `arguments` here are the tool parameters
(query text, client_id), which are not secrets. If a tool ever took secrets, redact first.
"""

from __future__ import annotations

from app.core.db import SessionLocal
from app.models.mcp_audit import McpAuditLog


async def record_tool_call(
    *,
    tool_name: str,
    arguments: dict,
    tenant_id: str | None,
    user_id: str | None,
    outcome: str,
    error: str | None = None,
) -> None:
    """Persist a single MCP tool-call audit entry (best-effort durable write)."""
    async with SessionLocal() as session:
        session.add(
            McpAuditLog(
                tenant_id=tenant_id,
                user_id=user_id,
                tool_name=tool_name,
                arguments=arguments,
                outcome=outcome,
                error=error,
            )
        )
        await session.commit()
