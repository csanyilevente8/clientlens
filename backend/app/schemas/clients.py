"""Client API schemas (request/response DTOs, separate from the ORM model)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ClientCreate(BaseModel):
    """Request body for creating a client. Note: no tenant_id — it is resolved
    server-side from the authenticated user, never accepted from the client (§16)."""

    name: str


class ClientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # allow building from ORM objects

    id: str
    tenant_id: str
    name: str
    created_at: datetime
    updated_at: datetime
