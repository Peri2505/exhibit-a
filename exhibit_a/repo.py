"""Getting a target repo onto disk and reading its source files."""
from __future__ import annotations

import asyncio
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .config import settings

SOURCE_EXTS = {".py"}
SKIP_DIRS = {".git", "node_modules", "venv", ".venv", "env", "__pycache__", "dist",
             "build", ".tox", ".mypy_cache", ".pytest_cache", "site-packages", "migrations"}
GITHUB_RE = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?(\.git)?/?$")


@dataclass
class SourceFile:
    path: str      # relative, posix
    text: str

    @property
    def numbered(self) -> str:
        return "\n".join(f"{i + 1:4d}| {line}" for i, line in enumerate(self.text.splitlines()))


async def clone(url: str, dest: Path) -> Path:
    if not GITHUB_RE.match(url):
        raise ValueError("Only public https://github.com/<owner>/<repo> URLs are supported.")
    proc = await asyncio.create_subprocess_exec(
        "git", "clone", "--depth", "1", url, str(dest),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    out, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"git clone failed: {out.decode(errors='replace')[-400:]}")
    return dest


def copy_tree(src: Path, dest: Path) -> Path:
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns(
        ".git", "__pycache__", ".pytest_cache", "*.db", ".venv", "venv", "node_modules"))
    return dest


def make_workdir(prefix: str = "exhibit-") -> Path:
    return Path(tempfile.mkdtemp(prefix=prefix))


def is_test_path(rel: str) -> bool:
    parts = rel.split("/")
    name = parts[-1]
    return ("tests" in parts or "test" in parts or name.startswith("test_")
            or name.endswith("_test.py") or name == "conftest.py")


def read_sources(root: Path) -> list[SourceFile]:
    files: list[SourceFile] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in SOURCE_EXTS:
            continue
        rel = path.relative_to(root).as_posix()
        if any(part in SKIP_DIRS for part in rel.split("/")) or is_test_path(rel):
            continue
        if path.stat().st_size > settings.max_file_bytes:
            continue
        try:
            files.append(SourceFile(rel, path.read_text(encoding="utf-8")))
        except UnicodeDecodeError:
            continue
        if len(files) >= settings.max_files:
            break
    return files


def read_test_context(root: Path, limit_chars: int = 6000) -> str:
    """conftest files and one example test, so the model learns the project's test style."""
    chunks: list[str] = []
    for path in sorted(root.rglob("conftest.py")):
        rel = path.relative_to(root).as_posix()
        if any(p in SKIP_DIRS for p in rel.split("/")):
            continue
        chunks.append(f"### {rel}\n{path.read_text(encoding='utf-8', errors='replace')}")
    examples = [p for p in sorted(root.rglob("test_*.py"))
                if not any(s in SKIP_DIRS or s == "exhibit_a" for s in p.relative_to(root).parts)]
    if examples:
        p = examples[0]
        chunks.append(f"### {p.relative_to(root).as_posix()}\n"
                      f"{p.read_text(encoding='utf-8', errors='replace')}")
    text = "\n\n".join(chunks)
    return text[:limit_chars] if text else "(no existing tests)"


def tree_listing(root: Path, limit: int = 150) -> str:
    out = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if any(p in SKIP_DIRS for p in rel.split("/")) or path.is_dir():
            continue
        out.append(rel)
        if len(out) >= limit:
            out.append("...")
            break
    return "\n".join(out)
