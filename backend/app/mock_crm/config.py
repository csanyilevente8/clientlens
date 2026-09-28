"""Configuration for the mock CRM service.

Kept separate from the main app's Settings: the mock CRM is a *simulated external
system*, deployed as its own container. It must be configurable to misbehave on
demand so the (future) CRM sync worker's retry / backoff / circuit-breaker / DLQ
logic can be exercised against it (failure scenario F, SYSTEMDESING §11-12).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class MockCRMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MOCK_CRM_", env_file=".env", extra="ignore")

    service_name: str = "mock-crm"
    version: str = "0.1.0"

    # Fraction of write requests that fail with 503 (0.0 = never, 1.0 = always).
    # Lets us reproduce "the CRM is flaky/unavailable" without touching client code.
    failure_rate: float = 0.0

    # Artificial latency added to every request, in milliseconds. Useful for
    # exercising client timeouts and the circuit breaker's slow-call detection.
    latency_ms: int = 0


@lru_cache
def get_mock_crm_settings() -> MockCRMSettings:
    return MockCRMSettings()
