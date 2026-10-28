"""The Exhibit A orchestrator.

Pipeline, per target repo:
  1. Nano   — triage every source file by risk
  2. Super  — analyze the top suspects into concrete, testable findings
  3. Ultra  — for each finding: write a proof test, run it (must FAIL),
              then write a patch, run it (proof must PASS, suite stays green)

A finding is only reported once a test has demonstrated it. Anything we can't
prove is dropped. Everything runs against a copy of the repo in an offline sandbox.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import settings
from .events import EventBus
from .llm import TokenFactoryClient, extract_json, strip_reasoning
from .repo import (SourceFile, copy_tree, make_workdir, read_sources,
                   read_test_context, tree_listing)
from .sandbox import Sandbox, TestRun
from . import prompts


@dataclass
class Finding:
    id: str
    title: str
    category: str
    cwe: str
    severity: str
    path: str
    line: int
    evidence: str
    explanation: str
    expected_secure_behavior: str
    stage: str = "suspected"          # suspected → proven → patched → verified | dismissed
    claim: str = ""
    test_path: str = ""
    test_code: str = ""
    patch_summary: str = ""
    diff: str = ""
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _slug(text: str, n: int = 40) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:n] or "finding"


class ExhibitAgent:
    def __init__(self, client: TokenFactoryClient, bus: EventBus) -> None:
        self.client = client
        self.bus = bus
        self.findings: list[Finding] = []

    async def scan(self, repo_url: str | None = None, local_path: str | None = None) -> list[Finding]:
        workdir = make_workdir()
        repo_root = workdir / "repo"
        deps_dir = workdir / "deps"
        try:
            await self._materialize(repo_url, local_path, repo_root)
            sources = read_sources(repo_root)
            self.bus.emit("scan.loaded", file_count=len(sources),
                          files=[f.path for f in sources])
            if not sources:
                self.bus.emit("scan.done", proven=0, verified=0, reason="no source files")
                return []

            sandbox = await Sandbox.create(deps_dir)
            self.bus.emit("sandbox.ready", mode=sandbox.mode)
            if sandbox.mode == "docker":
                self.bus.emit("sandbox.deps", status=await sandbox.install_deps(repo_root))

            baseline = await sandbox.pytest(repo_root, self._suite_targets(repo_root))
            self.bus.emit("suite.baseline", status=baseline.status, summary=baseline.summary)

            suspects = await self._triage(sources)
            findings = await self._analyze(repo_root, sources, suspects)

            for finding in findings[: settings.max_findings]:
                self.findings.append(finding)
                await self._prosecute(repo_root, sandbox, baseline, finding)

            proven = sum(f.stage in ("proven", "patched", "verified") for f in self.findings)
            verified = sum(f.stage == "verified" for f in self.findings)
            self.bus.emit("scan.done", proven=proven, verified=verified,
                          total=len(self.findings))
            return self.findings
        finally:
            self.bus.emit("usage.final", usage={r: asdict(u) for r, u in self.client.usage.items()})

    # ---- stage 0: get the code ------------------------------------------------
    async def _materialize(self, repo_url, local_path, repo_root: Path) -> None:
        if local_path:
            src = Path(local_path).expanduser().resolve()
            if not src.is_dir():
                raise ValueError(f"Not a directory: {src}")
            self.bus.emit("scan.start", source=str(src), kind="local")
            copy_tree(src, repo_root)
        elif repo_url:
            self.bus.emit("scan.start", source=repo_url, kind="git")
            from .repo import clone
            await clone(repo_url, repo_root)
        else:
            raise ValueError("Provide repo_url or local_path.")

    def _suite_targets(self, repo_root: Path) -> list[str]:
        return ["."] if list(repo_root.rglob("test_*.py")) else []

    # ---- stage 1: triage (Nano) ----------------------------------------------
    async def _triage(self, sources: list[SourceFile]) -> list[str]:
        previews = "\n\n".join(
            f"### {f.path}\n" + "\n".join(f.text.splitlines()[:40]) for f in sources)
        self.bus.emit("stage", stage="triage", role="nano",
                      message=f"Triaging {len(sources)} files for risk")
        raw = await self.client.chat(
            "nano", "triage", prompts.TRIAGE_SYSTEM,
            prompts.TRIAGE_USER.format(previews=previews[:60000]), max_tokens=2000)
        try:
            data = extract_json(raw)
            ranked = sorted(data.get("files", []), key=lambda x: x.get("risk", 0), reverse=True)
        except Exception as exc:  # noqa: BLE001
            self.bus.emit("stage.warn", stage="triage", message=f"triage parse failed: {exc}")
            ranked = [{"path": f.path, "risk": 5, "reason": "fallback"} for f in sources]
        known = {f.path for f in sources}
        suspects = [r["path"] for r in ranked
                    if r.get("path") in known and r.get("risk", 0) >= 3][: settings.max_suspects]
        if not suspects:
            suspects = [f.path for f in sources][: settings.max_suspects]
        self.bus.emit("triage.result",
                      ranked=[{"path": r.get("path"), "risk": r.get("risk"),
                               "reason": r.get("reason", "")} for r in ranked[:12]],
                      suspects=suspects)
        return suspects

    # ---- stage 2: analysis (Super) -------------------------------------------
    async def _analyze(self, repo_root: Path, sources: list[SourceFile],
                       suspects: list[str]) -> list[Finding]:
        tree = tree_listing(repo_root)
        by_path = {f.path: f for f in sources}
        findings: list[Finding] = []
        for path in suspects:
            sf = by_path[path]
            self.bus.emit("stage", stage="analyze", role="super",
                          message=f"Analyzing {path}", path=path)
            raw = await self.client.chat(
                "super", f"analyze:{path}", prompts.ANALYZE_SYSTEM.format(
                    max_findings=settings.max_findings),
                prompts.ANALYZE_USER.format(tree=tree, path=path, numbered=sf.numbered),
                max_tokens=4000)
            try:
                items = extract_json(raw).get("findings", [])
            except Exception as exc:  # noqa: BLE001
                self.bus.emit("stage.warn", stage="analyze", path=path, message=str(exc))
                continue
            for item in items:
                fid = f"F{len(findings) + 1:02d}"
                finding = Finding(
                    id=fid, title=item.get("title", "Untitled"),
                    category=item.get("category", "other"), cwe=item.get("cwe", "CWE-?"),
                    severity=item.get("severity", "medium"), path=path,
                    line=int(item.get("line", 0) or 0), evidence=item.get("evidence", ""),
                    explanation=item.get("explanation", ""),
                    expected_secure_behavior=item.get("expected_secure_behavior", ""))
                findings.append(finding)
                self.bus.emit("finding.suspected", finding=finding.to_dict())
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        findings.sort(key=lambda f: order.get(f.severity, 9))
        return findings

    # ---- stage 3: prove + patch (Ultra) --------------------------------------
    async def _prosecute(self, repo_root: Path, sandbox: Sandbox, baseline: TestRun,
                         finding: Finding) -> None:
        sf_path = repo_root / finding.path
        source = (repo_root / finding.path).read_text(encoding="utf-8", errors="replace")
        numbered = SourceFile(finding.path, source).numbered
        tree = tree_listing(repo_root)
        test_ctx = read_test_context(repo_root)
        test_dir = repo_root / "tests" / "exhibit_a"
        test_dir.mkdir(parents=True, exist_ok=True)
        (test_dir / "__init__.py").write_text("")
        test_name = f"test_{finding.id.lower()}_{_slug(finding.title, 30)}"
        test_file = test_dir / f"{test_name}.py"
        rel_test = test_file.relative_to(repo_root).as_posix()

        # --- write a proof test that fails on the vulnerable code ---
        retry = ""
        proved = False
        for attempt in range(1, settings.proof_attempts + 1):
            self.bus.emit("stage", stage="prove", role="ultra",
                          message=f"{finding.id}: writing proof test (attempt {attempt})",
                          finding_id=finding.id)
            raw = await self.client.chat(
                "ultra", f"prove:{finding.id}", prompts.PROVE_SYSTEM.format(test_name=test_name),
                prompts.PROVE_USER.format(
                    title=finding.title, cwe=finding.cwe, severity=finding.severity,
                    path=finding.path, line=finding.line, evidence=finding.evidence,
                    expected=finding.expected_secure_behavior, tree=tree,
                    test_context=test_ctx, numbered=numbered, retry=retry),
                max_tokens=4000)
            try:
                data = extract_json(raw)
                code = strip_reasoning(data["test_code"])
                finding.claim = data.get("claim", "")
            except Exception as exc:  # noqa: BLE001
                retry = prompts.PROVE_RETRY.format(status="invalid JSON", output=str(exc)[:500])
                continue
            test_file.write_text(code)
            finding.test_code = code
            finding.test_path = rel_test
            run = await sandbox.pytest(repo_root, [rel_test])
            self.bus.emit("prove.run", finding_id=finding.id, attempt=attempt,
                          status=run.status, summary=run.summary)
            if run.status == "failed":   # exactly what we want: proof fails on vuln code
                proved = True
                break
            if run.status == "passed":
                finding.note = "Proof test passed on current code — not a vulnerability."
                retry = prompts.PROVE_RETRY.format(status="test PASSED (nothing proven)",
                                                   output=run.output)
            else:
                retry = prompts.PROVE_RETRY.format(status=run.status, output=run.output)

        if not proved:
            finding.stage = "dismissed"
            finding.note = finding.note or "Could not produce a reliable failing proof."
            if test_file.exists():
                test_file.unlink()
            self.bus.emit("finding.dismissed", finding=finding.to_dict())
            return

        finding.stage = "proven"
        self.bus.emit("finding.proven", finding=finding.to_dict())

        # --- patch until the proof passes and the suite stays green ---
        before = source
        retry = ""
        for attempt in range(1, settings.patch_attempts + 1):
            self.bus.emit("stage", stage="patch", role="ultra",
                          message=f"{finding.id}: writing patch (attempt {attempt})",
                          finding_id=finding.id)
            raw = await self.client.chat(
                "ultra", f"patch:{finding.id}", prompts.PATCH_SYSTEM,
                prompts.PATCH_USER.format(
                    title=finding.title, cwe=finding.cwe, explanation=finding.explanation,
                    test_code=finding.test_code, path=finding.path,
                    source=(repo_root / finding.path).read_text(errors="replace"), retry=retry),
                max_tokens=6000)
            try:
                data = extract_json(raw)
                changed = data["files"]
                finding.patch_summary = data.get("summary", "")
            except Exception as exc:  # noqa: BLE001
                retry = prompts.PATCH_RETRY.format(result="invalid JSON", output=str(exc)[:400])
                continue

            backups = self._apply(repo_root, changed)
            proof = await sandbox.pytest(repo_root, [rel_test])
            suite = await sandbox.pytest(repo_root, self._suite_targets(repo_root))
            suite_ok = suite.status in ("passed", "no_tests") and suite.failed == 0
            self.bus.emit("patch.run", finding_id=finding.id, attempt=attempt,
                          proof_status=proof.status, suite_status=suite.status,
                          suite_summary=suite.summary)
            if proof.status == "passed" and suite_ok:
                finding.stage = "verified"
                finding.diff = self._diff(finding.path, before,
                                          (repo_root / finding.path).read_text(errors="replace"))
                self.bus.emit("finding.verified", finding=finding.to_dict())
                return
            # revert and retry
            self._restore(backups)
            problem = ("proof still fails" if proof.status != "passed"
                       else f"regressions in suite ({suite.summary})")
            retry = prompts.PATCH_RETRY.format(
                result=problem, output=(proof.output if proof.status != "passed" else suite.output))

        finding.stage = "patched"
        finding.note = "Proven, but no patch passed verification. Reported for manual fix."
        self.bus.emit("finding.patch_failed", finding=finding.to_dict())

    def _apply(self, repo_root: Path, files: list[dict]) -> list[tuple[Path, str | None]]:
        backups: list[tuple[Path, str | None]] = []
        for f in files:
            target = (repo_root / f["path"]).resolve()
            if repo_root.resolve() not in target.parents and target != repo_root.resolve():
                continue  # never write outside the repo
            backups.append((target, target.read_text() if target.exists() else None))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f["content"])
        return backups

    def _restore(self, backups: list[tuple[Path, str | None]]) -> None:
        for path, original in backups:
            if original is None:
                path.unlink(missing_ok=True)
            else:
                path.write_text(original)

    def _diff(self, path: str, before: str, after: str) -> str:
        import difflib
        return "".join(difflib.unified_diff(
            before.splitlines(keepends=True), after.splitlines(keepends=True),
            fromfile=f"a/{path}", tofile=f"b/{path}"))
