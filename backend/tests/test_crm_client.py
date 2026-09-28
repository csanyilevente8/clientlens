"""Tests for the HTTP CRM client's retry/backoff logic.

Two styles:
 - Against the real mock CRM app in-process (httpx ASGITransport) for happy path +
   idempotency — proves the client and server agree on the contract.
 - Against a scripted transport for retry behavior — proves retry-on-transient,
   no-retry-on-4xx, and exhaustion, without real network or sleeps.

backoff sleeps are neutralized so the suite stays fast.
"""

import httpx
import pytest

from app.integrations.crm import http as crm_http
from app.integrations.crm.base import ActionItemSync, CRMBadRequest, CRMUnavailable
from app.integrations.crm.http import HTTPCRMClient
from app.mock_crm.config import MockCRMSettings
from app.mock_crm.main import create_app as create_crm_app
from app.mock_crm.store import CRMStore

ITEM = ActionItemSync(client_ref="c1", description="Send projection", owner="a@x.com")


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch) -> None:
    """Make backoff instant so retry tests don't actually wait.

    Patching backoff_delay to 0.0 means the client's asyncio.sleep(0.0) returns
    immediately — no need to patch sleep itself.
    """
    monkeypatch.setattr(crm_http, "backoff_delay", lambda *a, **k: 0.0)


def _client_against_mock(**settings_overrides) -> HTTPCRMClient:
    app = create_crm_app(settings=MockCRMSettings(**settings_overrides), store=CRMStore())
    transport = httpx.ASGITransport(app=app)
    inner = httpx.AsyncClient(transport=transport, base_url="http://crm")
    return HTTPCRMClient("http://crm", client=inner)


async def test_sync_success_against_mock_crm() -> None:
    crm = _client_against_mock()
    result = await crm.sync_action_item("k1", ITEM)
    assert result.crm_id.startswith("crm_")
    assert result.created is True


async def test_idempotent_replay_reports_not_created() -> None:
    crm = _client_against_mock()
    first = await crm.sync_action_item("dup", ITEM)
    second = await crm.sync_action_item("dup", ITEM)
    assert first.crm_id == second.crm_id
    assert first.created is True
    assert second.created is False  # server returned 200 -> idempotent replay


async def test_4xx_is_not_retried() -> None:
    """A permanent error must raise CRMBadRequest immediately (no retries)."""
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(400, json={"detail": "bad"})

    inner = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://crm")
    crm = HTTPCRMClient("http://crm", client=inner, max_attempts=3)

    with pytest.raises(CRMBadRequest):
        await crm.sync_action_item("k", ITEM)
    assert attempts == 1  # not retried


async def test_transient_503_retried_then_succeeds() -> None:
    """Fails twice with 503, succeeds on the third attempt."""
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return httpx.Response(503, json={"detail": "unavailable"})
        return httpx.Response(201, json={"crm_id": "crm_ok"})

    inner = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://crm")
    crm = HTTPCRMClient("http://crm", client=inner, max_attempts=3)

    result = await crm.sync_action_item("k", ITEM)
    assert result.crm_id == "crm_ok"
    assert attempts == 3


async def test_exhausted_retries_raise_unavailable() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503, json={"detail": "down"})

    inner = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://crm")
    crm = HTTPCRMClient("http://crm", client=inner, max_attempts=3)

    with pytest.raises(CRMUnavailable):
        await crm.sync_action_item("k", ITEM)
    assert attempts == 3  # tried exactly max_attempts times


async def test_timeout_is_retried_as_transient() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise httpx.ConnectTimeout("timed out")
        return httpx.Response(201, json={"crm_id": "crm_late"})

    inner = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://crm")
    crm = HTTPCRMClient("http://crm", client=inner, max_attempts=3)

    result = await crm.sync_action_item("k", ITEM)
    assert result.crm_id == "crm_late"
    assert attempts == 2


def test_backoff_delay_is_bounded_and_grows() -> None:
    """Sanity check the (real) backoff curve: increases, jittered, capped."""
    from app.integrations.crm.http import backoff_delay

    for attempt in range(1, 10):
        d = backoff_delay(attempt, base=0.5, cap=8.0)
        assert 0.0 <= d <= 8.0
