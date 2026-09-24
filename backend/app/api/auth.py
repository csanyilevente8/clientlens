from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, CurrentUserDep
from app.core.db import get_session
from app.core.security import create_access_token, verify_password
from app.models.tenants import Tenant
from app.models.users import User
from app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter(tags=["login"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]

@router.post("/api/v1/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: SessionDep) -> TokenResponse:
    # 1. find the tenant by slug
    tenant = (await session.execute(
        select(Tenant).where(Tenant.slug == payload.tenant_slug)
    )).scalar_one_or_none()

    # 2. find the user within that tenant
    #    (only if tenant exists — think about how to structure this)
    if tenant:
        user = (await session.execute(
            select(User).where(User.tenant_id == tenant.id, User.email == payload.email)
        )).scalar_one_or_none()
    else:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    # 3. verify the password against user.hashed_password
    if user:
        valid_password = verify_password(payload.password, user.hashed_password)
    else:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    # 4. on ANY failure (no tenant / no user / bad password):
    #    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    #    — same generic message for all, to avoid user enumeration
    if not valid_password:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    # 5. success: mint the token
    token = create_access_token(
        subject=user.id, tenant_id=user.tenant_id, role=user.role.value
    )
    return TokenResponse(access_token=token, token_type="bearer")


@router.get("/api/v1/auth/me", response_model=CurrentUser)
async def me(current_user: CurrentUserDep) -> CurrentUser:
    """Return the authenticated caller. Protected: requires a valid Bearer token.

    The protection is the CurrentUserDep parameter itself — FastAPI resolves it
    (extract token -> decode -> build CurrentUser) before this body runs, and 401s
    if the token is missing/invalid.
    """
    return current_user