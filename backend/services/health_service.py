from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse, urlunparse

import requests

from backend.paths import PROFILE_JSON, PROFILE_PATH, to_rel
from backend.services.config_service import get_public_smtp, get_send_config
from email_sends_db import get_db_path


def _alt_urls(base_url: str) -> list[str]:
    urls = [base_url.rstrip("/")]
    parsed = urlparse(base_url)
    host = (parsed.hostname or "").lower()
    if host == "localhost":
        swapped = parsed._replace(netloc=parsed.netloc.replace("localhost", "127.0.0.1", 1))
        urls.append(urlunparse(swapped).rstrip("/"))
    elif host == "127.0.0.1":
        swapped = parsed._replace(netloc=parsed.netloc.replace("127.0.0.1", "localhost", 1))
        urls.append(urlunparse(swapped).rstrip("/"))
    return list(dict.fromkeys(urls))


def _ollama_status(base_url: str) -> dict:
    models: list[str] = []
    for url in _alt_urls(base_url):
        try:
            resp = requests.get(f"{url}/api/tags", timeout=3)
            if not resp.ok:
                continue
            models = [item.get("name", "") for item in (resp.json().get("models") or []) if item.get("name")]
            return {"reachable": True, "models": models}
        except requests.RequestException:
            continue
    return {"reachable": False, "models": models}


def get_health() -> dict:
    smtp = get_public_smtp()
    config = get_send_config()
    db_path = get_db_path()
    if not db_path.is_absolute():
        from backend.paths import PROJECT_ROOT

        db_path = (PROJECT_ROOT / db_path).resolve()
    profile = Path(config["profile_file"])
    ollama = _ollama_status(config["ollama_base_url"])
    return {
        **smtp,
        "ollama_reachable": ollama["reachable"],
        "ollama_models": ollama["models"],
        "db_path": to_rel(db_path),
        "db_exists": db_path.is_file(),
        "profile_exists": PROFILE_JSON.is_file() or profile.is_file() or PROFILE_PATH.is_file(),
    }
