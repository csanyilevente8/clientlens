"""Structured LLM output schema (SPEC §15).

This is the CONTRACT the LLM must satisfy. Provider output is parsed into these Pydantic
models; validation failure means we do NOT persist it as trusted data (Rule 4).
"""

from pydantic import BaseModel


class Goal(BaseModel):
    description: str
    timeframe: str | None = None


class ActionItem(BaseModel):
    description: str
    owner: str | None = None


class LifeEvent(BaseModel):
    description: str


class MeetingAnalysis(BaseModel):
    summary: str
    topics: list[str] = []
    goals: list[Goal] = []
    concerns: list[str] = []
    action_items: list[ActionItem] = []
    life_events: list[LifeEvent] = []
