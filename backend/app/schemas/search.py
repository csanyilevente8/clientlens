"""Search / RAG API schemas."""

from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str
    client_id: str | None = None  # optional: scope to one client (still tenant-scoped)


class SearchSource(BaseModel):
    meeting_id: str
    client_id: str
    excerpt: str
    score: float  # lower distance = more relevant


class SearchResponse(BaseModel):
    answer: str
    sources: list[SearchSource]
