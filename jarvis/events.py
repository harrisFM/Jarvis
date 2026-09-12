"""A tiny async pub/sub bus. Every component publishes JSON-serialisable events; the dashboard
WebSocket and the CLI subscribe. Keeping text as the contract makes every stage observable."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

Event = dict[str, Any]
Handler = Callable[[Event], Awaitable[None]]


class EventBus:
    def __init__(self) -> None:
        self._handlers: list[Handler] = []
        self.history: list[Event] = []
        self.max_history = 500

    def subscribe(self, handler: Handler) -> Callable[[], None]:
        self._handlers.append(handler)

        def unsubscribe() -> None:
            if handler in self._handlers:
                self._handlers.remove(handler)

        return unsubscribe

    async def publish(self, type_: str, **data: Any) -> Event:
        event: Event = {"type": type_, "ts": time.time(), **data}
        self.history.append(event)
        if len(self.history) > self.max_history:
            del self.history[: len(self.history) - self.max_history]
        results = await asyncio.gather(*(h(event) for h in list(self._handlers)), return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):  # never let a bad subscriber break the pipeline
                pass
        return event
