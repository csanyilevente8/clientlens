"""Mock CRM service — a simulated external system.

This is NOT part of the ClientLens API. It stands in for a third-party CRM
(Salesforce/HubSpot-style) that the CRM sync worker pushes action items into. It runs
as its own container (see docker-compose `mock-crm`) precisely so we can treat it like
a real external dependency: reachable over HTTP, occasionally slow or unavailable, and
idempotent on retry.

Endpoints:
    GET  /health                 liveness
    POST /crm/action-items       create/sync a task (requires Idempotency-Key header)
    GET  /crm/action-items       list everything synced so far (inspection/tests)

Failure injection (so the worker's retry/backoff/circuit-breaker/DLQ can be exercised):
    - MOCK_CRM_FAILURE_RATE / MOCK_CRM_LATENCY_MS env vars (global default)
    - X-Mock-Fail: "1" request header forces a 503 for that single call
"""

from __future__ import annotations

import asyncio
import random
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException, Response, status

from app.mock_crm.config import MockCRMSettings, get_mock_crm_settings
from app.mock_crm.schemas import ActionItemResource, ActionItemSyncRequest, HealthResponse
from app.mock_crm.store import CRMStore


def create_app(settings: MockCRMSettings | None = None, store: CRMStore | None = None) -> FastAPI:
    settings = settings or get_mock_crm_settings()
    store = store if store is not None else CRMStore()

    app = FastAPI(title="Mock CRM", version=settings.version)
    # Expose for tests/inspection.
    app.state.settings = settings
    app.state.store = store

    async def _simulate_conditions(force_fail: bool) -> None:
        """Apply configured latency, then maybe fail — before doing real work.

        Failing *before* the store write matters: a 503 must mean 'nothing happened',
        so the caller can safely retry with the same Idempotency-Key.
        """
        if settings.latency_ms > 0:
            await asyncio.sleep(settings.latency_ms / 1000)
        if force_fail or (settings.failure_rate > 0 and random.random() < settings.failure_rate):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="CRM temporarily unavailable",
            )

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", service=settings.service_name, version=settings.version)

    @app.post("/crm/action-items", response_model=ActionItemResource)
    async def sync_action_item(
        payload: ActionItemSyncRequest,
        response: Response,
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
        force_fail: Annotated[str | None, Header(alias="X-Mock-Fail")] = None,
    ) -> ActionItemResource:
        # A real CRM would key idempotency off a header; we require it so retries are safe.
        if not idempotency_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Idempotency-Key header is required",
            )

        await _simulate_conditions(force_fail == "1")

        resource, created = store.upsert_action_item(idempotency_key, payload)
        # 201 on first create, 200 on idempotent replay — lets the caller/tests observe
        # that a retry did not create a duplicate.
        response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return resource

    @app.get("/crm/action-items", response_model=list[ActionItemResource])
    def list_action_items() -> list[ActionItemResource]:
        return store.list_action_items()

    return app


app = create_app()
