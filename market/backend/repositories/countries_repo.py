from __future__ import annotations

from backend.clock import new_id, now_iso
from backend.db import connect


def list_for_user(user_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, label, location_line, phone
            FROM countries
            WHERE user_id = ?
            ORDER BY created_at ASC
            """,
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get(user_id: str, country_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, label, location_line, phone
            FROM countries
            WHERE user_id = ? AND id = ?
            """,
            (user_id, country_id),
        ).fetchone()
    return dict(row) if row else None


def create(user_id: str, label: str, location_line: str, phone: str) -> dict:
    country_id = new_id()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO countries (id, user_id, label, location_line, phone, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (country_id, user_id, label, location_line, phone, now_iso()),
        )
    return {"id": country_id, "label": label, "location_line": location_line, "phone": phone}


def update(user_id: str, country_id: str, label: str, location_line: str, phone: str) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE countries
            SET label = ?, location_line = ?, phone = ?
            WHERE user_id = ? AND id = ?
            """,
            (label, location_line, phone, user_id, country_id),
        )


def delete(user_id: str, country_id: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM countries WHERE user_id = ? AND id = ?", (user_id, country_id))
