"""Offline replay: re-emit a recorded run's events on the original timeline.

Used for the demo UI and the video when no live API key is present, and for
testing the server without calling Token Factory. A recorded run is just the
newline-delimited JSON the EventBus writes to runs/<name>/events.jsonl.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from .events import EventBus


def load_events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


async def replay(events: list[dict], bus: EventBus, speed: float = 1.0,
                 max_gap: float = 1.5) -> None:
    """Emit recorded events, preserving (capped) inter-event timing."""
    prev_t = 0.0
    for event in events:
        gap = min(event.get("t", prev_t) - prev_t, max_gap)
        prev_t = event.get("t", prev_t)
        if gap > 0:
            await asyncio.sleep(gap / max(speed, 0.01))
        payload = {k: v for k, v in event.items() if k not in ("t",)}
        type_ = payload.pop("type")
        bus.emit(type_, **payload)
    bus.close()


def latest_run(runs_dir: Path) -> Path | None:
    runs = sorted((p for p in runs_dir.glob("*/events.jsonl")),
                  key=lambda p: p.stat().st_mtime, reverse=True)
    return runs[0] if runs else None
