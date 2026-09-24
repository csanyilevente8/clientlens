"""Meeting endpoints — tenant-scoped. Processing is SYNCHRONOUS here on purpose (§5).

The create endpoint blocks while the meeting is "analyzed" inline. This is the naive
Stage-1 design we will later replace with async processing (Kafka + worker) once we have
documented why (the bottleneck analysis in docs/capacity + docs/failure-scenarios).
"""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import ClientRepoDep, MeetingRepoDep, SessionDep
from app.models.meetings import Meeting
from app.schemas.meetings import MeetingCreate, MeetingResponse
from app.services.meeting_processing import process_meeting_sync

router = APIRouter(prefix="/api/v1/meetings", tags=["meetings"])


@router.post("", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
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
    )  # tenant_id set by the repository
    created = await meetings.add(meeting)

    # SYNCHRONOUS processing, in-request (the §5 bottleneck). The response waits for this.
    await process_meeting_sync(created)

    await session.commit()
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
