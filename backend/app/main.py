"""Application entrypoint and FastAPI app factory."""

from fastapi import FastAPI

from app.api.health import router as health_router
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
    return app


app = create_app()
