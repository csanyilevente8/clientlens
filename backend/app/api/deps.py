from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import decode_access_token
from app.integrations.embeddings.factory import get_embedding_provider
from app.integrations.llm.base import LLMProvider
from app.integrations.llm.factory import get_llm_provider
from app.integrations.vectorstore.pgvector import VectorStore
from app.repositories.clients import ClientRepository
from app.repositories.meetings import MeetingRepository
from app.services.retrieval import RetrievalService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

SessionDep = Annotated[AsyncSession, Depends(get_session)]

class CurrentUser(BaseModel):
    user_id: str
    tenant_id: str
    role: str

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> CurrentUser:
    try:
        claims = decode_access_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    return CurrentUser(
        user_id=claims["sub"],
        tenant_id=claims["tenant_id"],
        role=claims["role"],
    )

CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


async def get_client_repository(
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ClientRepository:
    """Build a ClientRepository bound to the authenticated caller's tenant.

    The tenant_id comes only from the verified token (via CurrentUser) — never from the
    request. Endpoints depend on this, so every client query is auto-scoped to the tenant.
    """
    return ClientRepository(session, current_user.tenant_id)


ClientRepoDep = Annotated[ClientRepository, Depends(get_client_repository)]


async def get_meeting_repository(
    session: SessionDep,
    current_user: CurrentUserDep,
) -> MeetingRepository:
    """MeetingRepository bound to the authenticated caller's tenant."""
    return MeetingRepository(session, current_user.tenant_id)


MeetingRepoDep = Annotated[MeetingRepository, Depends(get_meeting_repository)]

LLMProviderDep = Annotated[LLMProvider, Depends(get_llm_provider)]


async def get_retrieval_service(session: SessionDep) -> RetrievalService:
    """Build the RetrievalService with the embedder, vector store, and LLM."""
    return RetrievalService(
        session=session,
        embedder=get_embedding_provider(),
        store=VectorStore(),
        llm=get_llm_provider(),
    )


RetrievalServiceDep = Annotated[RetrievalService, Depends(get_retrieval_service)]