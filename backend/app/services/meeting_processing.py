"""Synchronous AI analysis of a meeting (SYSTEMDESING §5 Stage 1 — still inline/blocking).

Flow (SPEC §15-17):
  provider.analyze_meeting(transcript) -> MeetingAnalysis (Pydantic-validated)
    -> on failure: status = FAILED, persist NO intelligence (LLM output untrusted, Rule 4)
    -> on success: persist summary + provenance on the meeting, insert intelligence rows
       (each tracing back to this meeting), status = COMPLETED

Still runs in-request (the bottleneck we analysed). Phase 3 moves it to a worker.
"""

from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.llm.base import ClientContext, LLMProvider
from app.models.intelligence import (
    ActionItem,
    ClientConcern,
    ClientGoal,
    LifeEvent,
    MeetingTopic,
)
from app.models.meeting_status import MeetingStatus
from app.models.meetings import Meeting


async def analyze_meeting(
    meeting: Meeting, session: AsyncSession, provider: LLMProvider
) -> None:
    """Run analysis for a meeting and persist the results (via the given session)."""
    meeting.status = MeetingStatus.PROCESSING

    try:
        analysis = await provider.analyze_meeting(
            meeting.transcript, ClientContext(client_id=meeting.client_id)
        )
    except (ValidationError, ValueError):
        # LLM produced invalid/unusable output — do not persist partial "trusted" data.
        meeting.status = MeetingStatus.FAILED
        return

    # Persist provenance on the meeting (SPEC §16).
    meeting.summary = analysis.summary
    meeting.model = provider.model
    meeting.model_version = provider.model_version
    meeting.prompt_version = provider.prompt_version
    meeting.processing_timestamp = datetime.now(UTC)

    # Persist extracted intelligence, each row tracing back to this meeting (provenance).
    def prov() -> dict[str, str]:
        return {
            "tenant_id": meeting.tenant_id,
            "meeting_id": meeting.id,
            "client_id": meeting.client_id,
        }

    for topic in analysis.topics:
        session.add(MeetingTopic(**prov(), topic=topic))
    for goal in analysis.goals:
        session.add(ClientGoal(**prov(), description=goal.description, timeframe=goal.timeframe))
    for concern in analysis.concerns:
        session.add(ClientConcern(**prov(), description=concern))
    for item in analysis.action_items:
        session.add(ActionItem(**prov(), description=item.description, owner=item.owner))
    for event in analysis.life_events:
        session.add(LifeEvent(**prov(), description=event.description))

    meeting.status = MeetingStatus.COMPLETED
