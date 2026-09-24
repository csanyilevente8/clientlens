"""Synchronous meeting processing — DELIBERATELY NAIVE (SYSTEMDESING §5, Stage 1).

This runs the "analysis" INLINE within the create-meeting request. It is intentionally the
wrong design for production: the API blocks until analysis finishes. We build it this way
first so the bottleneck is real and observable (§5 Stage 2), which justifies moving to
asynchronous processing (Kafka + worker) later — rather than adding that complexity blindly.

For now the "analysis" is a stand-in (a sleep + status transition). Phase 2 replaces it with
the real LLMProvider abstraction; Phase 3 moves it off the request path entirely.
"""

import asyncio

from app.models.meeting_status import MeetingStatus
from app.models.meetings import Meeting

# Simulated processing time. Real LLM analysis can take many seconds — this makes the
# synchronous-blocking problem tangible during Stage 2 analysis.
SIMULATED_ANALYSIS_SECONDS = 2.0


async def process_meeting_sync(meeting: Meeting) -> None:
    """Mutate the meeting through its processing lifecycle, in-request (blocking).

    CREATED -> PROCESSING -> COMPLETED. On this synchronous path, the HTTP request does
    not return until this finishes.
    """
    meeting.status = MeetingStatus.PROCESSING
    # Stand-in for the LLM call + embedding + extraction that Phase 2/4 will add.
    await asyncio.sleep(SIMULATED_ANALYSIS_SECONDS)
    meeting.status = MeetingStatus.COMPLETED
