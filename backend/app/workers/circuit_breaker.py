"""A minimal circuit breaker (SYSTEMDESING §11-12).

Purpose in ClientLens: stop the CRM sync worker from hammering a CRM that has been
failing, and — crucially — signal the worker to PAUSE consumption while open, so Kafka
buffers the backlog until the CRM recovers (keeping the "eventual sync" promise, failure
scenario F). It reacts ONLY to transient failures; permanent (4xx) failures are
dead-lettered by the worker and never reach the breaker.

States:
    CLOSED     — calls allowed. `failure_threshold` consecutive failures -> OPEN.
    OPEN       — calls short-circuited. After `reset_timeout` seconds -> HALF_OPEN.
    HALF_OPEN  — allow ONE trial call. Success -> CLOSED; failure -> OPEN (reset timer).

Time is injectable (`clock`) so tests are deterministic without sleeping.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from enum import Enum


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        reset_timeout: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._reset_timeout = reset_timeout
        self._clock = clock
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at: float | None = None

    @property
    def state(self) -> CircuitState:
        # OPEN transitions to HALF_OPEN lazily once the cool-down has elapsed.
        if (
            self._state is CircuitState.OPEN
            and self._opened_at is not None
            and self._clock() - self._opened_at >= self._reset_timeout
        ):
            self._state = CircuitState.HALF_OPEN
        return self._state

    def allows_request(self) -> bool:
        """Whether a call may proceed. Reading `state` first applies the timed transition."""
        return self.state is not CircuitState.OPEN

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self._state = CircuitState.CLOSED
        self._opened_at = None

    def record_failure(self) -> None:
        # A failure during HALF_OPEN re-opens immediately (the probe failed).
        if self.state is CircuitState.HALF_OPEN:
            self._trip()
            return
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._failure_threshold:
            self._trip()

    def _trip(self) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = self._clock()

    def seconds_until_retry(self) -> float:
        """How long until an OPEN breaker will allow a trial call (0 if not open)."""
        if self._state is not CircuitState.OPEN or self._opened_at is None:
            return 0.0
        return max(0.0, self._reset_timeout - (self._clock() - self._opened_at))
