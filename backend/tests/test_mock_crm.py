"""Tests for the mock CRM service.

The mock CRM has no database, so these use a plain (sync) TestClient with fresh app
instances — no MySQL needed. We build the app with an explicit settings/store so each
test controls failure injection in isolation.
"""

from fastapi.testclient import TestClient

from app.mock_crm.config import MockCRMSettings
from app.mock_crm.main import create_app
from app.mock_crm.store import CRMStore

PAYLOAD = {
    "client_ref": "client-123",
    "description": "Send retirement projection",
    "owner": "advisor@example.com",
    "due_date": "2026-10-15",
}


def _client(**settings_overrides) -> TestClient:
    settings = MockCRMSettings(**settings_overrides)
    return TestClient(create_app(settings=settings, store=CRMStore()))


def test_health_ok() -> None:
    resp = _client().get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "mock-crm"


def test_create_action_item_returns_201_with_crm_id() -> None:
    resp = _client().post(
        "/crm/action-items", json=PAYLOAD, headers={"Idempotency-Key": "k1"}
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["crm_id"].startswith("crm_")
    assert body["client_ref"] == "client-123"
    assert body["description"] == "Send retirement projection"


def test_missing_idempotency_key_is_rejected() -> None:
    resp = _client().post("/crm/action-items", json=PAYLOAD)
    assert resp.status_code == 400


def test_same_idempotency_key_does_not_duplicate() -> None:
    """The core guarantee: a retry with the same key returns the same resource.

    This is what makes the future CRM worker's at-least-once retries safe.
    """
    client = _client()
    first = client.post("/crm/action-items", json=PAYLOAD, headers={"Idempotency-Key": "dup"})
    second = client.post("/crm/action-items", json=PAYLOAD, headers={"Idempotency-Key": "dup"})

    assert first.status_code == 201
    assert second.status_code == 200  # idempotent replay
    assert first.json()["crm_id"] == second.json()["crm_id"]

    listed = client.get("/crm/action-items").json()
    assert len(listed) == 1


def test_different_keys_create_distinct_items() -> None:
    client = _client()
    a = client.post("/crm/action-items", json=PAYLOAD, headers={"Idempotency-Key": "a"})
    b = client.post("/crm/action-items", json=PAYLOAD, headers={"Idempotency-Key": "b"})
    assert a.json()["crm_id"] != b.json()["crm_id"]
    assert len(client.get("/crm/action-items").json()) == 2


def test_forced_failure_header_returns_503_and_writes_nothing() -> None:
    """A 503 must mean 'nothing happened' so the caller can safely retry."""
    client = _client()
    resp = client.post(
        "/crm/action-items",
        json=PAYLOAD,
        headers={"Idempotency-Key": "k", "X-Mock-Fail": "1"},
    )
    assert resp.status_code == 503
    assert client.get("/crm/action-items").json() == []


def test_failure_rate_1_always_fails() -> None:
    client = _client(failure_rate=1.0)
    resp = client.post("/crm/action-items", json=PAYLOAD, headers={"Idempotency-Key": "k"})
    assert resp.status_code == 503


def test_retry_after_failure_succeeds_with_same_key() -> None:
    """Simulates worker behavior: fail once, then retry the same key -> single item."""
    client = _client()
    failed = client.post(
        "/crm/action-items",
        json=PAYLOAD,
        headers={"Idempotency-Key": "retry-1", "X-Mock-Fail": "1"},
    )
    assert failed.status_code == 503

    ok = client.post(
        "/crm/action-items", json=PAYLOAD, headers={"Idempotency-Key": "retry-1"}
    )
    assert ok.status_code == 201
    assert len(client.get("/crm/action-items").json()) == 1
