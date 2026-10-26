from __future__ import annotations

import os

import bcrypt
from cryptography.fernet import Fernet, InvalidToken

from backend.paths import DATA_DIR

SESSION_COOKIE = "session"
SESSION_DAYS = 14


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def _fernet() -> Fernet:
    key = os.environ.get("FERNET_KEY", "").strip()
    if not key:
        path = DATA_DIR / ".fernet_key"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            key = path.read_text(encoding="utf-8").strip()
        else:
            key = Fernet.generate_key().decode()
            path.write_text(key, encoding="utf-8")
    try:
        return Fernet(key.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise RuntimeError("FERNET_KEY is not a valid Fernet key.") from exc


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Saved mailbox password could not be read. Save the mailbox again.") from exc
