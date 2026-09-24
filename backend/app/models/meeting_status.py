import enum


class MeetingStatus(str, enum.Enum):
    """Lifecycle of a meeting's processing (SPEC §11).

    CREATED    -> just ingested, not yet processed
    PROCESSING -> analysis in progress
    COMPLETED  -> structured intelligence extracted and persisted
    FAILED     -> processing failed (e.g. LLM error / invalid output)
    """

    CREATED = "CREATED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
