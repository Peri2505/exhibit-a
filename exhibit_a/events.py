"""A tiny event bus. The agent emits events; the UI and the recorder consume them."""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Callable


class EventBus:
    def __init__(self, record_to: Path | None = None) -> None:
        self.history: list[dict[str, Any]] = []
        self._subscribers: list[asyncio.Queue] = []
        self._listeners: list[Callable[[dict], None]] = []
        self._record_to = record_to
        self._t0 = time.time()
        self.closed = False
        if record_to:
            record_to.parent.mkdir(parents=True, exist_ok=True)
            record_to.write_text("")

    def emit(self, type_: str, **data: Any) -> dict[str, Any]:
        event = {"type": type_, "t": round(time.time() - self._t0, 3), **data}
        self.history.append(event)
        if self._record_to:
            with self._record_to.open("a") as fh:
                fh.write(json.dumps(event) + "\n")
        for q in list(self._subscribers):
            q.put_nowait(event)
        for fn in self._listeners:
            fn(event)
        return event

    def on(self, fn: Callable[[dict], None]) -> None:
        self._listeners.append(fn)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        for e in self.history:
            q.put_nowait(e)
        if self.closed:
            q.put_nowait(None)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    def close(self) -> None:
        self.closed = True
        for q in list(self._subscribers):
            q.put_nowait(None)
