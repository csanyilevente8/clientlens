"""Search / RAG endpoint (SPEC §26).

Tenant-scoped: the tenant comes from the authenticated user (CurrentUser), never the
request body. Retrieval + RAG live in RetrievalService (§19: callers go through the service
layer, not the DB/vector store directly).
"""

from fastapi import APIRouter

from app.api.deps import CurrentUserDep, RetrievalServiceDep
from app.schemas.search import SearchRequest, SearchResponse, SearchSource

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def search(
    payload: SearchRequest,
    current_user: CurrentUserDep,
    retrieval: RetrievalServiceDep,
) -> SearchResponse:
    result = await retrieval.answer(
        tenant_id=current_user.tenant_id,  # tenant from the token, never the request
        query=payload.query,
        client_id=payload.client_id,
    )
    return SearchResponse(
        answer=result.answer,
        sources=[
            SearchSource(
                meeting_id=h.meeting_id,
                client_id=h.client_id,
                excerpt=h.content[:200],
                score=h.distance,
            )
            for h in result.sources
        ],
    )
