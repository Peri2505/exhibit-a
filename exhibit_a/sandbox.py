"""Run pytest against a copy of the target repo, isolated from the host.

Docker mode (preferred): tests run in a throwaway container with no network,
capped memory/CPU, and a read-only dependency layer. Dependencies are installed
once per scan in a separate step that is the only one allowed network access.

Local mode (fallback for dev machines without Docker): tests run in a
subprocess with a scrubbed environment (no API keys) and a hard timeout.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from .config import settings

REPORT_NAME = ".exhibit_report.xml"


@dataclass
class TestRun:
    __test__ = False  # not a pytest test class
    status: str              # "passed" | "failed" | "error" | "timeout" | "no_tests"
    passed: int = 0
    failed: int = 0
    errors: int = 0
    output: str = ""
    failures: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return f"{self.passed} passed, {self.failed} failed, {self.errors} errors"


async def docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    proc = await asyncio.create_subprocess_exec(
        "docker", "info", stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    return (await proc.wait()) == 0


class Sandbox:
    def __init__(self, mode: str, deps_dir: Path | None = None) -> None:
        self.mode = mode
        self.deps_dir = deps_dir

    @classmethod
    async def create(cls, deps_dir: Path) -> "Sandbox":
        mode = settings.sandbox
        if mode == "auto":
            mode = "docker" if await docker_available() else "local"
        return cls(mode, deps_dir)

    async def install_deps(self, repo: Path) -> str:
        """Docker mode only: install requirements into a cache dir (the one networked step)."""
        req = repo / "requirements.txt"
        if self.mode != "docker" or not req.exists():
            return "skipped"
        self.deps_dir.mkdir(parents=True, exist_ok=True)
        cmd = ["docker", "run", "--rm",
               "-v", f"{repo.resolve()}:/work:ro", "-v", f"{self.deps_dir.resolve()}:/deps",
               settings.sandbox_image,
               "pip", "install", "--quiet", "--no-cache-dir", "--target", "/deps",
               "-r", "/work/requirements.txt"]
        rc, out = await _run(cmd, cwd=repo, timeout=600, env=None)
        return "ok" if rc == 0 else f"failed: {out[-300:]}"

    async def pytest(self, repo: Path, targets: list[str]) -> TestRun:
        report = repo / REPORT_NAME
        if report.exists():
            report.unlink()
        args = ["-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=short",
                f"--junitxml={REPORT_NAME}", *targets]
        if self.mode == "docker":
            cmd = ["docker", "run", "--rm", "--network", "none",
                   "--memory", "768m", "--cpus", "1", "--pids-limit", "256",
                   "--security-opt", "no-new-privileges", "--cap-drop", "ALL",
                   "-v", f"{repo.resolve()}:/work", "-w", "/work"]
            if self.deps_dir and self.deps_dir.exists():
                cmd += ["-v", f"{self.deps_dir.resolve()}:/deps:ro", "-e", "PYTHONPATH=/deps"]
            cmd += [settings.sandbox_image, "python", *args]
            env = None
        else:
            cmd = [sys.executable, *args]
            env = _scrubbed_env()
        rc, out = await _run(cmd, cwd=repo, timeout=settings.test_timeout_s, env=env)
        if rc == -1:
            return TestRun("timeout", output=out)
        return _parse(rc, out, report)


def _scrubbed_env() -> dict[str, str]:
    keep = {"PATH", "HOME", "LANG", "LC_ALL", "PYTHONPATH", "SYSTEMROOT", "TMPDIR", "VIRTUAL_ENV"}
    env = {k: v for k, v in os.environ.items() if k in keep}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


async def _run(cmd: list[str], cwd: Path, timeout: int, env: dict | None) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd, cwd=str(cwd), env=env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return -1, f"Timed out after {timeout}s"
    return proc.returncode, out.decode(errors="replace")


def _parse(rc: int, output: str, report: Path) -> TestRun:
    tail = output[-6000:]
    if rc == 5:
        return TestRun("no_tests", output=tail)
    passed = failed = errors = 0
    failures: list[str] = []
    if report.exists():
        try:
            root = ET.parse(report).getroot()
            for case in root.iter("testcase"):
                name = case.get("name", "?")
                if case.find("failure") is not None:
                    failed += 1
                    failures.append(name)
                elif case.find("error") is not None:
                    errors += 1
                    failures.append(name)
                elif case.find("skipped") is None:
                    passed += 1
        except ET.ParseError:
            pass
    if rc == 0:
        status = "passed"
    elif failed and not errors:
        status = "failed"
    else:
        # collection/import errors, fixture errors, crashes
        status = "error"
    return TestRun(status, passed, failed, errors, tail, failures)
