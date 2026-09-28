"""LLM provider abstraction (SPEC §14, §46; Rule 3).

Business logic depends on the LLMProvider protocol, never on a vendor SDK. Providers are
selected by config (LLM_PROVIDER). MockLLMProvider is the default for dev and all tests.

Java/Spring analog: an interface with multiple beans chosen by a config property.
"""

from typing import Protocol

from pydantic import BaseModel

from app.schemas.analysis import MeetingAnalysis


class ClientContext(BaseModel):
    """Minimal context passed to the LLM alongside the transcript."""

    client_id: str
    client_name: str | None = None


class LLMProvider(Protocol):
    """The interface all providers implement.

    Also exposes provenance metadata (model / version / prompt_version) so the caller can
    record HOW an analysis was produced (SPEC §16).
    """

    model: str
    model_version: str
    prompt_version: str

    async def analyze_meeting(
        self, transcript: str, context: ClientContext
    ) -> MeetingAnalysis: ...

    async def answer_question(self, question: str, context: str) -> str:
        """Answer a question grounded in the provided retrieved context (RAG)."""
        ...
