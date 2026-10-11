"""Structured (JSON) logging with a correlation id (SPEC §30; production engineering).

Every log line is a JSON object on stdout — machine-parseable for log aggregation (Cloud
Logging / ELK). A **correlation id** is carried in a context var and injected into every
record, so all logs for one request (and, when propagated through the event payload, one
meeting's whole async pipeline across workers) share an id — this is what makes "debug one
request across services" (SPEC §30/§31 Q29) possible without a full tracing backend.
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from contextvars import ContextVar

# The correlation id for the current request/task. Set by middleware (API) or per-event
# (workers); read by the log formatter.
correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def new_correlation_id() -> str:
    return uuid.uuid4().hex


def set_correlation_id(value: str | None) -> str:
    """Set the current correlation id (generating one if None). Returns the id used."""
    cid = value or new_correlation_id()
    correlation_id.set(cid)
    return cid


def get_correlation_id() -> str | None:
    return correlation_id.get()


class JsonFormatter(logging.Formatter):
    """Render log records as single-line JSON, including the correlation id + any extras."""

    _RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
        "message", "asctime", "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id.get(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Include structured extras passed via logger.info(..., extra={...}).
        for key, value in record.__dict__.items():
            if key not in self._RESERVED and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Install the JSON formatter on the root logger (idempotent)."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]  # replace any default handlers
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
