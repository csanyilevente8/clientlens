from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from app.core.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

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