from __future__ import annotations

import sqlite3

from backend.clock import new_id, now_iso
from backend.db import connect


def create(email: str, password_hash: str) -> dict:
    user_id = new_id()
    created = now_iso()
    try:
        with connect() as conn:
            conn.execute(
                "INSERT INTO users (id, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (user_id, email, password_hash, created),
            )
            conn.execute(
                "INSERT INTO profiles (user_id, updated_at) VALUES (?, ?)",
                (user_id, created),
            )
    except sqlite3.IntegrityError as exc:
        raise ValueError("An account with that email already exists.") from exc
    return {"id": user_id, "email": email}


def get_by_email(email: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT id, email, password_hash FROM users WHERE email = ?", (email,)).fetchone()
    return dict(row) if row else None


def get_by_id(user_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT id, email FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def public_user(row: dict) -> dict:
    return {"id": row["id"], "email": row["email"]}
