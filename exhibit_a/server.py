"""FastAPI server: serves the case-file UI and streams agent events over SSE."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .agent import ExhibitAgent
from .config import settings
from .events import EventBus
from .llm import LLMError, TokenFactoryClient
from .replay import latest_run, load_events, replay

STATIC = Path(__file__).resolve().parent / "web"
app = FastAPI(title="Exhibit A")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/config")
async def config() -> dict:
    return {
        "models": {r: {"model_id": s.model_id, "job": s.job,
                       "input_per_m": s.input_per_m, "output_per_m": s.output_per_m}
                   for r, s in settings.models.items()},
        "has_api_key": bool(settings.api_key),
        "has_recorded_run": latest_run(settings.runs_dir) is not None,
    }


async def _sse(bus: EventBus, task: asyncio.Task | None):
    q = bus.subscribe()
    try:
        while True:
            event = await q.get()
            if event is None:
                yield "event: end\ndata: {}\n\n"
                break
            yield f"data: {json.dumps(event)}\n\n"
    finally:
        bus.unsubscribe(q)
        if task and not task.done():
            task.cancel()


@app.get("/api/scan")
async def scan(request: Request, repo: str | None = None, local: str | None = None,
               demo: bool = False, speed: float = 1.0):
    bus = EventBus()

    if demo or not settings.api_key:
        run = latest_run(settings.runs_dir)
        if run is None:
            async def empty():
                bus.emit("error", message="No recorded run to replay and no API key set.")
                bus.close()
                async for m in _sse(bus, None):
                    yield m
            return StreamingResponse(empty(), media_type="text/event-stream")
        events = load_events(run)
        task = asyncio.create_task(replay(events, bus, speed=max(0.05, min(speed, 5.0))))
        return StreamingResponse(_sse(bus, task), media_type="text/event-stream")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = settings.runs_dir / f"{stamp}-live"
    bus = EventBus(record_to=run_dir / "events.jsonl")

    async def drive():
        client = TokenFactoryClient(bus=bus)
        agent = ExhibitAgent(client, bus)
        try:
            await agent.scan(repo_url=repo, local_path=local)
        except (LLMError, Exception) as exc:  # noqa: BLE001
            bus.emit("error", message=str(exc))
        finally:
            await client.aclose()
            bus.close()

    task = asyncio.create_task(drive())
    return StreamingResponse(_sse(bus, task), media_type="text/event-stream")


if STATIC.exists():
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
