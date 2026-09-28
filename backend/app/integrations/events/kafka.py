"""Kafka implementation of EventBus (aiokafka)."""

from aiokafka import AIOKafkaProducer

from app.core.config import get_settings


class KafkaEventBus:
    def __init__(self) -> None:
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=get_settings().kafka_bootstrap_servers,
            # Wait for the broker to ack the write before considering it published.
            acks="all",
            enable_idempotence=True,
        )
        await self._producer.start()

    async def stop(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None

    async def publish(self, topic: str, key: str, value: bytes) -> None:
        if self._producer is None:
            raise RuntimeError("KafkaEventBus not started")
        # Keying by aggregate id -> same-meeting events land on the same partition (order).
        await self._producer.send_and_wait(topic, key=key.encode(), value=value)
