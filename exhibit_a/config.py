"""Configuration. Everything is overridable with environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_dotenv() -> None:
    """Tiny .env loader so we don't need python-dotenv."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


@dataclass(frozen=True)
class ModelSpec:
    role: str          # "nano" | "super" | "ultra"
    model_id: str
    input_per_m: float  # USD per 1M input tokens
    output_per_m: float  # USD per 1M output tokens
    job: str            # what this tier does in the pipeline


def _f(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    base_url: str = os.environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1")
    api_key: str = os.environ.get("NEBIUS_API_KEY", "")

    models: dict = field(default_factory=lambda: {
        "nano": ModelSpec(
            "nano",
            os.environ.get("EXHIBIT_NANO_MODEL", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"),
            _f("EXHIBIT_NANO_IN", 0.06), _f("EXHIBIT_NANO_OUT", 0.24),
            "Fast triage: rank every file by security risk",
        ),
        "super": ModelSpec(
            "super",
            os.environ.get("EXHIBIT_SUPER_MODEL", "nvidia/nemotron-3-super-120b-a12b"),
            _f("EXHIBIT_SUPER_IN", 0.30), _f("EXHIBIT_SUPER_OUT", 0.90),
            "Analysis: turn risky files into concrete, testable hypotheses",
        ),
        "ultra": ModelSpec(
            "ultra",
            # Confirm the exact ID with:  python -m exhibit_a models
            os.environ.get("EXHIBIT_ULTRA_MODEL", "nvidia/Nemotron-3-Ultra-550B-A55B"),
            _f("EXHIBIT_ULTRA_IN", 1.00), _f("EXHIBIT_ULTRA_OUT", 3.00),
            "Deep reasoning: write the proof test, then the patch",
        ),
    })

    max_files: int = int(os.environ.get("EXHIBIT_MAX_FILES", 60))
    max_file_bytes: int = int(os.environ.get("EXHIBIT_MAX_FILE_BYTES", 40_000))
    max_suspects: int = int(os.environ.get("EXHIBIT_MAX_SUSPECTS", 5))
    max_findings: int = int(os.environ.get("EXHIBIT_MAX_FINDINGS", 6))
    proof_attempts: int = int(os.environ.get("EXHIBIT_PROOF_ATTEMPTS", 2))
    patch_attempts: int = int(os.environ.get("EXHIBIT_PATCH_ATTEMPTS", 2))
    test_timeout_s: int = int(os.environ.get("EXHIBIT_TEST_TIMEOUT", 90))

    # "auto" uses Docker if a daemon is reachable, otherwise a local subprocess.
    sandbox: str = os.environ.get("EXHIBIT_SANDBOX", "auto")
    sandbox_image: str = os.environ.get("EXHIBIT_SANDBOX_IMAGE", "exhibit-a-sandbox:latest")

    runs_dir: Path = Path(os.environ.get(
        "EXHIBIT_RUNS_DIR", Path(__file__).resolve().parent.parent / "runs"))


settings = Settings()
