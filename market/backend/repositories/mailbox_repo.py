from __future__ import annotations

from backend.clock import now_iso
from backend.db import connect


def get(user_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM mailboxes WHERE user_id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def upsert(
    user_id: str,
    *,
    host: str,
    port: int,
    username: str,
    from_name: str,
    from_email: str,
    password_encrypted: str,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO mailboxes (
              user_id, host, port, username, from_name, from_email, password_encrypted, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
              host = excluded.host,
              port = excluded.port,
              username = excluded.username,
              from_name = excluded.from_name,
              from_email = excluded.from_email,
              password_encrypted = excluded.password_encrypted,
              updated_at = excluded.updated_at
            """,
            (user_id, host, port, username, from_name, from_email, password_encrypted, now_iso()),
        )
