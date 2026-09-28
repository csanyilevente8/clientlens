"""Circuit breaker unit tests (no DB, deterministic clock — no real sleeping)."""

from app.workers.circuit_breaker import CircuitBreaker, CircuitState


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def test_starts_closed_and_allows_requests() -> None:
    cb = CircuitBreaker(failure_threshold=3, reset_timeout=30.0, clock=FakeClock())
    assert cb.state is CircuitState.CLOSED
    assert cb.allows_request() is True


def test_opens_after_threshold_consecutive_failures() -> None:
    cb = CircuitBreaker(failure_threshold=3, reset_timeout=30.0, clock=FakeClock())
    cb.record_failure()
    cb.record_failure()
    assert cb.state is CircuitState.CLOSED  # not yet
    cb.record_failure()
    assert cb.state is CircuitState.OPEN
    assert cb.allows_request() is False


def test_success_resets_failure_count() -> None:
    cb = CircuitBreaker(failure_threshold=3, reset_timeout=30.0, clock=FakeClock())
    cb.record_failure()
    cb.record_failure()
    cb.record_success()  # counter back to 0
    cb.record_failure()
    cb.record_failure()
    assert cb.state is CircuitState.CLOSED  # only 2 since reset


def test_open_transitions_to_half_open_after_timeout() -> None:
    clock = FakeClock()
    cb = CircuitBreaker(failure_threshold=1, reset_timeout=30.0, clock=clock)
    cb.record_failure()  # trips (threshold=1)
    assert cb.state is CircuitState.OPEN
    assert cb.allows_request() is False

    clock.advance(29.0)
    assert cb.allows_request() is False  # still cooling down
    clock.advance(1.0)
    assert cb.state is CircuitState.HALF_OPEN
    assert cb.allows_request() is True  # one trial call permitted


def test_half_open_success_closes() -> None:
    clock = FakeClock()
    cb = CircuitBreaker(failure_threshold=1, reset_timeout=10.0, clock=clock)
    cb.record_failure()
    clock.advance(10.0)
    assert cb.state is CircuitState.HALF_OPEN
    cb.record_success()
    assert cb.state is CircuitState.CLOSED


def test_half_open_failure_reopens_and_resets_timer() -> None:
    clock = FakeClock()
    cb = CircuitBreaker(failure_threshold=1, reset_timeout=10.0, clock=clock)
    cb.record_failure()
    clock.advance(10.0)
    assert cb.state is CircuitState.HALF_OPEN
    cb.record_failure()  # probe failed
    assert cb.state is CircuitState.OPEN
    # Timer reset: needs another full cool-down.
    clock.advance(9.0)
    assert cb.allows_request() is False
    clock.advance(1.0)
    assert cb.state is CircuitState.HALF_OPEN


def test_seconds_until_retry_counts_down() -> None:
    clock = FakeClock()
    cb = CircuitBreaker(failure_threshold=1, reset_timeout=30.0, clock=clock)
    cb.record_failure()
    assert cb.seconds_until_retry() == 30.0
    clock.advance(12.0)
    assert cb.seconds_until_retry() == 18.0
