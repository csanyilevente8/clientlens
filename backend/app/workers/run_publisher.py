"""Entrypoint: outbox publisher process (drains outbox -> Kafka)."""

import asyncio

from app.core.db import SessionLocal
from app.integrations.events.kafka import KafkaEventBus
from app.workers.outbox_publisher import run_publisher_loop


def main() -> None:
    asyncio.run(run_publisher_loop(SessionLocal, KafkaEventBus()))


if __name__ == "__main__":
    main()
