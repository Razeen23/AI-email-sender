from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()

DATA_DIR = Path(os.environ.get("MARKET_DATA_DIR", ROOT / "data")).resolve()


def ollama_base_url() -> str:
    return os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")


def ollama_model() -> str:
    return os.environ.get("OLLAMA_MODEL", "llama3.2")


def daily_cap() -> int:
    raw = os.environ.get("DAILY_SEND_CAP", "25")
    try:
        return max(1, int(raw))
    except ValueError:
        return 25


def send_delay_seconds() -> int:
    raw = os.environ.get("SEND_DELAY_SECONDS", "10")
    try:
        return max(0, int(raw))
    except ValueError:
        return 10
