"""Application entrypoint and FastAPI app factory."""

from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.auth import router as auth_router
from app.api.clients import router as clients_router
from app.api.health import router as health_router
from app.api.meetings import router as meetings_router
from app.api.search import router as search_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.middleware import ObservabilityMiddleware


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    Using an app factory (rather than a module-level global) keeps construction
    explicit and testable — tests can build isolated app instances.
    """
    settings = get_settings()
    configure_logging()  # structured JSON logs on stdout (SPEC §30)

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
    )
    # Observability: correlation id + access logging + RED metrics (SPEC §30).
    app.add_middleware(ObservabilityMiddleware)

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(clients_router)
    app.include_router(meetings_router)
    app.include_router(search_router)

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        """Prometheus scrape endpoint."""
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
