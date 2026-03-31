import asyncio
from collections import defaultdict


class EventBus:
    def __init__(self):
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)

    async def emit(self, channel: str, event: dict) -> None:
        for queue in self._subscribers.get(channel, []):
            await queue.put(event)

    async def subscribe(self, channel: str):
        queue = asyncio.Queue()
        self._subscribers[channel].append(queue)
        try:
            while True:
                event = await queue.get()
                yield event
        finally:
            self._subscribers[channel].remove(queue)


event_bus = EventBus()
