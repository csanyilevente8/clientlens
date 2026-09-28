"""Meeting API schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.meeting_status import MeetingStatus


class MeetingCreate(BaseModel):
    """Request to create a meeting. tenant_id is NOT accepted — resolved server-side."""

    client_id: str
    title: str
    occurred_at: datetime
    transcript: str


class GoalOut(BaseModel):
    description: str
    timeframe: str | None = None


class ActionItemOut(BaseModel):
    description: str
    owner: str | None = None


class MeetingIntelligenceResponse(BaseModel):
    """The structured intelligence extracted from a meeting."""

    meeting_id: str
    status: MeetingStatus
    summary: str | None = None
    topics: list[str] = []
    goals: list[GoalOut] = []
    concerns: list[str] = []
    action_items: list[ActionItemOut] = []
    life_events: list[str] = []


class MeetingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    client_id: str
    title: str
    occurred_at: datetime
    status: MeetingStatus
    created_at: datetime
    updated_at: datetime
