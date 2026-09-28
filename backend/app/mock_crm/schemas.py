"""Request/response models for the mock CRM API.

The contract mirrors what a real CRM (e.g. Salesforce/HubSpot "task" or "activity")
would expose: create a task against a contact, get an opaque external id back. The
ClientLens CRM sync worker will map extracted ActionItems onto this shape.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class ActionItemSyncRequest(BaseModel):
    """A single action item to sync into the CRM.

    `client_ref` is the advisor's client identifier (ClientLens client_id). The CRM
    treats it as an opaque external reference used to attach the task to a contact.
    """

    client_ref: str = Field(..., min_length=1, max_length=64)
    description: str = Field(..., min_length=1, max_length=1000)
    owner: str | None = Field(default=None, max_length=255)
    due_date: str | None = Field(default=None, max_length=32)


class ActionItemResource(BaseModel):
    """What the CRM stores/returns for a synced action item."""

    crm_id: str
    client_ref: str
    description: str
    owner: str | None = None
    due_date: str | None = None
    created_at: datetime


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
