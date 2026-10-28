"""Command line entry point.

  python -m exhibit_a models                     list model IDs Token Factory serves
  python -m exhibit_a scan --local <dir>         scan a local directory
  python -m exhibit_a scan --repo <github-url>   clone and scan a public repo
  python -m exhibit_a serve                      start the case-file UI
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from .agent import ExhibitAgent
from .config import settings
from .events import EventBus
from .llm import TokenFactoryClient


def _run_dir(name: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    d = settings.runs_dir / f"{stamp}-{name}"
    d.mkdir(parents=True, exist_ok=True)
    return d


async def _models() -> int:
    client = TokenFactoryClient()
    try:
        ids = await client.list_models()
    finally:
        await client.aclose()
    print(f"{len(ids)} models on {settings.base_url}:\n")
    for i in ids:
        tag = next((f"  <-- {r} tier" for r, s in settings.models.items()
                    if s.model_id.lower() == i.lower()), "")
        print(f"  {i}{tag}")
    configured = {s.model_id.lower() for s in settings.models.values()}
    missing = configured - {i.lower() for i in ids}
    if missing:
        print("\n! These configured IDs were NOT found. Set EXHIBIT_*_MODEL in .env:")
        for m in missing:
            print(f"    {m}")
    return 0


async def _scan(args) -> int:
    name = (args.repo or args.local or "scan").rstrip("/").split("/")[-1]
    run_dir = _run_dir(name)
    bus = EventBus(record_to=run_dir / "events.jsonl")

    def log(e: dict) -> None:
        if e["type"] in ("stage", "finding.proven", "finding.verified",
                         "finding.dismissed", "finding.patch_failed", "scan.done",
                         "suite.baseline", "sandbox.ready"):
            print(f"[{e['t']:7.1f}s] {e['type']:22} "
                  f"{e.get('message') or e.get('finding', {}).get('title', '') or e.get('summary','')}")

    bus.on(log)
    client = TokenFactoryClient(bus=bus)
    agent = ExhibitAgent(client, bus)
    try:
        findings = await agent.scan(repo_url=args.repo, local_path=args.local)
    finally:
        await client.aclose()
        bus.close()

    report = {
        "source": args.repo or args.local,
        "findings": [f.to_dict() for f in findings],
        "usage": {r: vars(u) for r, u in client.usage.items()},
    }
    (run_dir / "report.json").write_text(json.dumps(report, indent=2))
    for f in findings:
        if f.stage == "verified":
            (run_dir / f"{f.id}.patch").write_text(f.diff)

    verified = [f for f in findings if f.stage == "verified"]
    print(f"\n{'='*60}\nProven: {sum(f.stage!='dismissed' for f in findings)}   "
          f"Verified fixes: {len(verified)}   "
          f"Total cost: ${sum(u.cost for u in client.usage.values()):.4f}")
    print(f"Report: {run_dir / 'report.json'}")
    return 0


def _serve(args) -> int:
    import uvicorn
    print(f"Case-file UI on http://127.0.0.1:{args.port}")
    uvicorn.run("exhibit_a.server:app", host="127.0.0.1", port=args.port, log_level="warning")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="exhibit_a", description="Exhibit A security agent")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("models", help="list Token Factory model IDs")
    s = sub.add_parser("scan", help="scan a repo")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--repo", help="public GitHub URL")
    g.add_argument("--local", help="local directory")
    srv = sub.add_parser("serve", help="run the case-file UI")
    srv.add_argument("--port", type=int, default=8000)

    args = parser.parse_args(argv)
    if args.cmd == "models":
        return asyncio.run(_models())
    if args.cmd == "scan":
        return asyncio.run(_scan(args))
    if args.cmd == "serve":
        return _serve(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
