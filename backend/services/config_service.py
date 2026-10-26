from __future__ import annotations

import os

from backend.paths import PROFILE_PATH, PROJECT_ROOT, RESUMES_DIR, load_dotenv

REQUIRED_SMTP = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "FROM_EMAIL")


def ensure_env() -> None:
    load_dotenv()


def smtp_configured() -> bool:
    ensure_env()
    return all(os.environ.get(key) for key in REQUIRED_SMTP)


def get_send_config() -> dict:
    ensure_env()
    return {
        "smtp_host": os.environ.get("SMTP_HOST", ""),
        "smtp_port": int(os.environ.get("SMTP_PORT") or "587"),
        "smtp_user": os.environ.get("SMTP_USER", ""),
        "smtp_password": os.environ.get("SMTP_PASSWORD", ""),
        "from_email": os.environ.get("FROM_EMAIL", ""),
        "resumes_base": str(RESUMES_DIR),
        "profile_file": str(PROJECT_ROOT / os.environ.get("PROFILE_FILE", PROFILE_PATH.name)),
        "ollama_base_url": (os.environ.get("OLLAMA_BASE_URL") or "http://127.0.0.1:11434")
        .replace("localhost", "127.0.0.1", 1)
        .rstrip("/"),
        "ollama_model": os.environ.get("OLLAMA_MODEL") or "llama3.2",
    }


def get_public_smtp() -> dict:
    config = get_send_config()
    return {
        "smtp_configured": smtp_configured(),
        "smtp_host": config["smtp_host"] or None,
        "smtp_port": config["smtp_port"],
        "from_email": config["from_email"] or None,
        "ollama_base_url": config["ollama_base_url"],
        "ollama_model": config["ollama_model"],
    }
