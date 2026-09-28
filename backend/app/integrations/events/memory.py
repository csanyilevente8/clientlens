"""In-memory EventBus for tests (no broker required)."""


class InMemoryEventBus:
    def __init__(self) -> None:
        # list of (topic, key, value) tuples that were "published"
        self.published: list[tuple[str, str, bytes]] = []

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def publish(self, topic: str, key: str, value: bytes) -> None:
        self.published.append((topic, key, value))
