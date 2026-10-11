"""Prometheus metrics (SPEC §30; production engineering).

Minimal RED-style metrics (Rate, Errors, Duration) for the HTTP API, exposed at /metrics
for a Prometheus scraper. Kept small on purpose — add more only when a real question needs
them (SPEC §20 "measure before optimizing").
"""

from prometheus_client import Counter, Histogram

# Rate + Errors: count requests, labeled by method / templated path / status.
http_requests_total = Counter(
    "clientlens_http_requests_total",
    "Total HTTP requests.",
    ["method", "path", "status"],
)

# Duration: request latency distribution, labeled by method / path.
http_request_duration_seconds = Histogram(
    "clientlens_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["method", "path"],
)
