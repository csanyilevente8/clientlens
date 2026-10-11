"""MCP authentication: resolve the caller's tenant from the request bearer token.

The MCP server is an application-layer BOUNDARY (SYSTEMDESIGN §19): the external reasoning
model (Claude) authenticates per request with a JWT, exactly like the REST API. We reuse
`decode_access_token` (RS256, verified with the PUBLIC key per ADR-009) so the MCP server
never holds the signing key.

Tenant isolation (ADR-008): the tenant_id comes ONLY from the verified token, never from a
tool argument — so a tool call can never ask for another tenant's data.
"""

from __future__ import annotations

from dataclasses import dataclass

import jwt
from mcp.server.fastmcp import Context

from app.core.security import decode_access_token


class MCPAuthError(Exception):
    """Raised when a request has no valid bearer token."""


@dataclass
class McpPrincipal:
    """The authenticated caller, derived from the JWT claims."""

    user_id: str
    tenant_id: str
    role: str


def _bearer_token_from_context(ctx: Context) -> str:
    """Pull the `Authorization: Bearer <jwt>` token out of the HTTP request.

    For the HTTP/SSE transport, the MCP request context carries the underlying Starlette
    request, whose headers hold the bearer token the client sent.
    """
    request = getattr(ctx.request_context, "request", None)
    if request is None:  # e.g. a non-HTTP transport — no request to read
        raise MCPAuthError("No HTTP request in context")
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise MCPAuthError("Missing or malformed Authorization header")
    return header[len("bearer ") :].strip()


def authenticate(ctx: Context) -> McpPrincipal:
    """Verify the request's bearer token and return the principal.

    Raises MCPAuthError on any failure (missing header, invalid/expired token). Tools
    translate that into a user-facing error result.
    """
    token = _bearer_token_from_context(ctx)
    try:
        claims = decode_access_token(token)
    except jwt.PyJWTError as exc:
        raise MCPAuthError(f"Invalid token: {exc}") from exc
    return McpPrincipal(
        user_id=claims["sub"],
        tenant_id=claims["tenant_id"],
        role=claims["role"],
    )
