"""Application entrypoint and FastAPI app factory."""

from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.clients import router as clients_router
from app.api.health import router as health_router
from app.api.meetings import router as meetings_router
from app.api.search import router as search_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    Using an app factory (rather than a module-level global) keeps construction
    explicit and testable — tests can build isolated app instances.
    """
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
    )
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(clients_router)
    app.include_router(meetings_router)
    app.include_router(search_router)
    return app


app = create_app()
