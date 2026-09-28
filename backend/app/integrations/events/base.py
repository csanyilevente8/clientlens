"""Event bus abstraction (SYSTEMDESING §7).

Business/publisher code depends on the EventBus protocol, not on aiokafka directly — so
tests can use an in-memory fake and we could swap brokers. Mirrors the LLMProvider pattern.

Topic naming follows SPEC §12.
"""

from typing import Protocol

# Topics (SPEC §12). Partitioned by aggregate id (meeting id) so events for the same
# meeting are ordered and consumers can scale across partitions.
TOPIC_MEETING_CREATED = "meeting.created"
# Emitted when analysis succeeds; consumed by the indexing worker (and later CRM sync).
TOPIC_INTELLIGENCE_EXTRACTED = "intelligence.extracted"
# Dead-letter topic: events that failed processing after all retries (§12).
TOPIC_MEETING_ANALYSIS_DLQ = "meeting.analysis.dlq"
# Dead-letter topic for the CRM sync worker: events whose CRM sync failed *permanently*
# (a 4xx from the CRM). Transient CRM outages are NOT dead-lettered — the breaker holds them.
TOPIC_CRM_SYNC_DLQ = "crm.sync.dlq"


class EventBus(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def publish(self, topic: str, key: str, value: bytes) -> None: ...
