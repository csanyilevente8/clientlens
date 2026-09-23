"""Health check endpoint.

A liveness signal used by local dev, Docker, and later Kubernetes probes (SPEC §30, §37).
Kept dependency-free so it stays green even if downstream services are unavailable.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session

router = APIRouter(tags=["health"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.version,
        environment=settings.environment,
    )


class ReadinessResponse(BaseModel):
    status: str
    database: str


@router.get("/ready", response_model=ReadinessResponse)
async def ready(session: SessionDep) -> ReadinessResponse:
    """Readiness probe: verifies the DB is reachable.

    Distinct from /health (liveness). K8s uses liveness to decide whether to restart a
    pod, and readiness to decide whether to route traffic (SPEC §37). A failing DB should
    make the pod NOT ready, but not necessarily restart it.
    """
    await session.execute(text("SELECT 1"))
    return ReadinessResponse(status="ready", database="ok")
