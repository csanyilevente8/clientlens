from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import decode_access_token
from app.repositories.clients import ClientRepository

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