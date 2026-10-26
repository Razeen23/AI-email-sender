from __future__ import annotations

import secrets

from backend.clock import expires_iso, now_iso
from backend.db import connect
from backend.repositories.users_repo import get_by_id
from backend.security import SESSION_DAYS


def create(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    with connect() as conn:
        conn.execute(
            "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user_id, expires_iso(SESSION_DAYS)),
        )
    return token


def user_for_token(token: str) -> dict | None:
    if not token:
        return None
    with connect() as conn:
        row = conn.execute(
            "SELECT user_id, expires_at FROM sessions WHERE token = ?",
            (token,),
        ).fetchone()
        if not row:
            return None
        user_id = row["user_id"]
        expires_at = row["expires_at"]
        if expires_at <= now_iso():
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            return None
    return get_by_id(user_id)


def delete(token: str) -> None:
    if not token:
        return
    with connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
