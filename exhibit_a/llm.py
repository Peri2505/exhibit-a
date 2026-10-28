"""Nebius Token Factory client (OpenAI-compatible) with per-tier usage tracking."""
from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from .config import ModelSpec, settings
from .events import EventBus


class LLMError(RuntimeError):
    pass


class ChatClient(Protocol):
    async def chat(self, role: str, purpose: str, system: str, user: str,
                   max_tokens: int = 4096, temperature: float = 0.2) -> str: ...


@dataclass
class Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    latency_ms_total: float = 0.0


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def strip_reasoning(text: str) -> str:
    text = _THINK_RE.sub("", text)
    # Some reasoning models leave an unterminated <think> block when truncated.
    if "<think>" in text.lower() and "</think>" not in text.lower():
        text = text[: text.lower().index("<think>")]
    return text.strip()


def extract_json(text: str) -> Any:
    """Pull the first JSON object/array out of a model reply, tolerating fences and chatter."""
    text = strip_reasoning(text)
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    candidates = [fence.group(1)] if fence else []
    candidates.append(text)
    for cand in candidates:
        cand = cand.strip()
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            pass
        # Honor whichever bracket opens first, so a top-level array isn't
        # mistaken for one of the objects inside it.
        obj_start, arr_start = cand.find("{"), cand.find("[")
        order = []
        if obj_start != -1:
            order.append((obj_start, "{", "}"))
        if arr_start != -1:
            order.append((arr_start, "[", "]"))
        for start, _opener, closer in sorted(order):
            end = cand.rfind(closer)
            if end > start:
                try:
                    return json.loads(cand[start: end + 1])
                except json.JSONDecodeError:
                    continue
    raise LLMError(f"Model did not return valid JSON. First 300 chars: {text[:300]!r}")


class TokenFactoryClient:
    """Routes each call to the Nemotron tier it belongs to and tracks cost/latency."""

    def __init__(self, bus: EventBus | None = None, models: dict[str, ModelSpec] | None = None,
                 api_key: str | None = None, base_url: str | None = None) -> None:
        self.models = models or settings.models
        self.api_key = api_key if api_key is not None else settings.api_key
        self.base_url = (base_url or settings.base_url).rstrip("/")
        self.bus = bus
        self.usage: dict[str, Usage] = {r: Usage() for r in self.models}
        if not self.api_key:
            raise LLMError("NEBIUS_API_KEY is not set. Copy .env.example to .env and add your key.")
        self._http = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=httpx.Timeout(300.0, connect=15.0),
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def chat(self, role: str, purpose: str, system: str, user: str,
                   max_tokens: int = 4096, temperature: float = 0.2) -> str:
        spec = self.models[role]
        payload = {
            "model": spec.model_id,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        delay = 2.0
        last_err: Exception | None = None
        for attempt in range(4):
            t0 = time.perf_counter()
            try:
                resp = await self._http.post("/chat/completions", json=payload)
            except httpx.HTTPError as exc:  # network hiccup
                last_err = exc
            else:
                if resp.status_code == 200:
                    latency_ms = (time.perf_counter() - t0) * 1000
                    body = resp.json()
                    text = body["choices"][0]["message"].get("content") or ""
                    usage = body.get("usage") or {}
                    self._record(spec, purpose, usage, latency_ms)
                    return text
                if resp.status_code in (429, 500, 502, 503, 504):
                    last_err = LLMError(f"{resp.status_code}: {resp.text[:200]}")
                else:
                    raise LLMError(
                        f"Token Factory returned {resp.status_code} for {spec.model_id}: "
                        f"{resp.text[:300]}")
            await asyncio.sleep(delay * (attempt + 1))
        raise LLMError(f"Token Factory call failed after retries: {last_err}")

    def _record(self, spec: ModelSpec, purpose: str, usage: dict, latency_ms: float) -> None:
        tin = int(usage.get("prompt_tokens", 0))
        tout = int(usage.get("completion_tokens", 0))
        cost = tin / 1e6 * spec.input_per_m + tout / 1e6 * spec.output_per_m
        u = self.usage[spec.role]
        u.calls += 1
        u.input_tokens += tin
        u.output_tokens += tout
        u.cost += cost
        u.latency_ms_total += latency_ms
        if self.bus:
            self.bus.emit("llm.call", role=spec.role, model=spec.model_id, purpose=purpose,
                          input_tokens=tin, output_tokens=tout,
                          cost=round(cost, 6), latency_ms=round(latency_ms))

    async def list_models(self) -> list[str]:
        resp = await self._http.get("/models")
        resp.raise_for_status()
        return sorted(m["id"] for m in resp.json().get("data", []))
