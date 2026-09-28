"""Meeting endpoints — tenant-scoped. Processing is SYNCHRONOUS here on purpose (§5).

The create endpoint blocks while the meeting is "analyzed" inline. This is the naive
Stage-1 design we will later replace with async processing (Kafka + worker) once we have
documented why (the bottleneck analysis in docs/capacity + docs/failure-scenarios).
"""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import ClientRepoDep, MeetingRepoDep, SessionDep
from app.models.intelligence import (
    ActionItem,
    ClientConcern,
    ClientGoal,
    LifeEvent,
    MeetingTopic,
)
from app.models.meetings import Meeting
from app.schemas.meetings import (
    ActionItemOut,
    GoalOut,
    MeetingCreate,
    MeetingIntelligenceResponse,
    MeetingResponse,
)
from app.services.outbox import MEETING_CREATED, add_outbox_event

router = APIRouter(prefix="/api/v1/meetings", tags=["meetings"])


@router.post("", response_model=MeetingResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_meeting(
    payload: MeetingCreate,
    meetings: MeetingRepoDep,
    clients: ClientRepoDep,
    session: SessionDep,
) -> Meeting:
    # Validate the client exists AND belongs to this tenant (clients repo is tenant-scoped,
    # so a client_id from another tenant simply won't be found -> 404).
    client = await clients.get(payload.client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client not found")

    meeting = Meeting(
        client_id=payload.client_id,
        title=payload.title,
        occurred_at=payload.occurred_at,
        transcript=payload.transcript,
    )  # tenant_id set by the repository, status defaults to CREATED
    created = await meetings.add(meeting)

    # Atomically stage the MeetingCreated event in the outbox (same transaction as the
    # meeting). Thin payload: the worker re-reads the transcript by id. Analysis now happens
    # asynchronously (worker), so we return 202 immediately instead of processing inline.
    add_outbox_event(
        session,
        event_type=MEETING_CREATED,
        aggregate_id=created.id,
        tenant_id=created.tenant_id,
        payload={"meeting_id": created.id, "tenant_id": created.tenant_id},
    )
    await session.commit()  # meeting + outbox event commit together (atomic)
    await session.refresh(created)
    return created


@router.get("", response_model=list[MeetingResponse])
async def list_meetings(meetings: MeetingRepoDep) -> list[Meeting]:
    return await meetings.list()


@router.get("/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(meeting_id: str, meetings: MeetingRepoDep) -> Meeting:
    meeting = await meetings.get(meeting_id)
    if meeting is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Meeting not found")
    return meeting


@router.get("/{meeting_id}/intelligence", response_model=MeetingIntelligenceResponse)
async def get_meeting_intelligence(
    meeting_id: str, meetings: MeetingRepoDep, session: SessionDep
) -> MeetingIntelligenceResponse:
    """Return the structured intelligence extracted from a meeting.

    Tenant-scoped: the meeting is fetched via the tenant-scoped repo first (404 if not this
    tenant's), so the intelligence rows we then read are guaranteed to be in-tenant.
    """
    meeting = await meetings.get(meeting_id)
    if meeting is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Meeting not found")

    async def rows(model):  # type: ignore[no-untyped-def]
        result = await session.execute(select(model).where(model.meeting_id == meeting_id))
        return list(result.scalars().all())

    return MeetingIntelligenceResponse(
        meeting_id=meeting_id,
        summary=meeting.summary,
        status=meeting.status,
        topics=[t.topic for t in await rows(MeetingTopic)],
        goals=[GoalOut(description=g.description, timeframe=g.timeframe) for g in await rows(ClientGoal)],
        concerns=[c.description for c in await rows(ClientConcern)],
        action_items=[ActionItemOut(description=a.description, owner=a.owner) for a in await rows(ActionItem)],
        life_events=[e.description for e in await rows(LifeEvent)],
    )
