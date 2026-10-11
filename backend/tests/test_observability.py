"""Observability tests: structured logging, correlation id, and /metrics (Phase 7)."""

import json
import logging

from fastapi.testclient import TestClient

from app.core.logging import JsonFormatter, get_correlation_id, set_correlation_id
from app.core.middleware import REQUEST_ID_HEADER
from app.main import create_app

client = TestClient(create_app())


# ---- structured logging ----

def test_json_formatter_emits_correlation_id_and_extras() -> None:
    set_correlation_id("cid-abc")
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "hello", (), None)
    record.meeting_id = "m-1"
    line = JsonFormatter().format(record)
    data = json.loads(line)  # must be valid single-line JSON
    assert data["message"] == "hello"
    assert data["level"] == "INFO"
    assert data["correlation_id"] == "cid-abc"
    assert data["meeting_id"] == "m-1"  # structured extra passed through


def test_set_correlation_id_generates_when_none() -> None:
    cid = set_correlation_id(None)
    assert cid and get_correlation_id() == cid


# ---- correlation id middleware ----

def test_response_echoes_generated_request_id() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.headers.get(REQUEST_ID_HEADER)  # one was generated and echoed


def test_response_preserves_incoming_request_id() -> None:
    resp = client.get("/health", headers={REQUEST_ID_HEADER: "my-trace-id"})
    assert resp.headers.get(REQUEST_ID_HEADER) == "my-trace-id"


# ---- metrics ----

def test_metrics_endpoint_exposes_prometheus_counters() -> None:
    client.get("/health")  # generate at least one request
    resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    assert "clientlens_http_requests_total" in body
    assert "clientlens_http_request_duration_seconds" in body
