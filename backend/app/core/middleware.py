"""Observability middleware: correlation id + request logging + metrics (SPEC §30).

One middleware does three things per request:
  1. establish a correlation id (from the X-Request-ID header, or generate one) and bind it
     to the logging context, echoing it back in the response header;
  2. time the request and record RED metrics (count + latency);
  3. emit one structured access-log line (method, path, status, duration, correlation id).

Metric labels use the matched route TEMPLATE (e.g. /api/v1/clients/{client_id}), not the raw
path, to keep label cardinality bounded.
"""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger, set_correlation_id
from app.core.metrics import http_request_duration_seconds, http_requests_total

logger = get_logger("clientlens.access")

REQUEST_ID_HEADER = "X-Request-ID"


def _route_template(request: Request) -> str:
    """The matched route path template, or the raw path if unmatched (bounded cardinality)."""
    route = request.scope.get("route")
    return getattr(route, "path", request.url.path)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        cid = set_correlation_id(request.headers.get(REQUEST_ID_HEADER))
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            duration = time.perf_counter() - start
            path = _route_template(request)
            http_requests_total.labels(request.method, path, str(status)).inc()
            http_request_duration_seconds.labels(request.method, path).observe(duration)
            logger.info(
                "http_request",
                extra={
                    "method": request.method,
                    "path": path,
                    "status": status,
                    "duration_ms": round(duration * 1000, 1),
                },
            )
            # Echo the correlation id so clients/other services can propagate it.
            try:
                response.headers[REQUEST_ID_HEADER] = cid
            except NameError:  # pragma: no cover — call_next raised; no response to tag
                pass
