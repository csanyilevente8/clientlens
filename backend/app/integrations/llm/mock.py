"""Deterministic, keyword-based mock LLM provider (default; used in dev and all tests).

It scans the transcript for known keywords and emits a plausible, DETERMINISTIC
MeetingAnalysis. Deterministic output makes tests stable and makes the SPEC §48 demo
scenario (business sale / succession / tax) actually produce sensible intelligence —
without any network call or cost.
"""

from app.integrations.llm.base import ClientContext
from app.schemas.analysis import ActionItem, Goal, LifeEvent, MeetingAnalysis

# keyword -> (topic, optional goal, optional concern, optional action item, optional life event)
# Kept simple and explicit so behavior is obvious and testable.
_TOPIC_KEYWORDS: dict[str, str] = {
    "business sale": "business sale",
    "sell": "business sale",
    "succession": "business succession",
    "son": "business succession",
    "retire": "retirement planning",
    "retirement": "retirement planning",
    "tax": "tax planning",
}
_CONCERN_KEYWORDS: dict[str, str] = {
    "tax": "tax implications",
    "worried": "general concern raised",
    "concern": "general concern raised",
}


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for i in items:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


class MockLLMProvider:
    model = "mock"
    model_version = "0.1.0"
    prompt_version = "v1"

    async def analyze_meeting(
        self, transcript: str, context: ClientContext
    ) -> MeetingAnalysis:
        text = transcript.lower()

        topics = _dedupe([t for kw, t in _TOPIC_KEYWORDS.items() if kw in text])
        concerns = _dedupe([c for kw, c in _CONCERN_KEYWORDS.items() if kw in text])

        goals: list[Goal] = []
        if "succession" in text or "son" in text:
            goals.append(Goal(description="Plan business succession", timeframe=None))
        if "sell" in text or "business sale" in text:
            goals.append(Goal(description="Explore business sale options", timeframe=None))

        action_items: list[ActionItem] = []
        if "tax" in text:
            action_items.append(
                ActionItem(description="Schedule tax planning discussion", owner="advisor")
            )

        life_events: list[LifeEvent] = []
        if "retire" in text or "retirement" in text:
            life_events.append(LifeEvent(description="Approaching retirement"))

        summary = f"Discussion covering: {', '.join(topics) if topics else 'general topics'}."

        return MeetingAnalysis(
            summary=summary,
            topics=topics,
            goals=goals,
            concerns=concerns,
            action_items=action_items,
            life_events=life_events,
        )

    async def answer_question(self, question: str, context: str) -> str:
        """Deterministic RAG answer for dev/tests.

        A real LLM would reason over `context` to answer `question`. The mock just states
        that the answer is grounded in the retrieved context (or says nothing was found),
        which is enough to exercise the RAG wiring deterministically.
        """
        if not context.strip():
            return "No relevant client history was found to answer this question."
        return (
            f"Based on the client's meeting history, here is what is relevant to "
            f"'{question}': {context[:400]}"
        )
