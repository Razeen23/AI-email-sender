from __future__ import annotations

from backend.clock import new_id, now_iso
from backend.db import connect


def _row(row) -> dict:
    item = dict(row)
    item["is_default"] = bool(item["is_default"])
    return item


def list_for_user(user_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, country_id, filename, extension, is_default, created_at
            FROM resumes
            WHERE user_id = ?
            ORDER BY created_at ASC
            """,
            (user_id,),
        ).fetchall()
    return [_row(row) for row in rows]


def list_for_country(user_id: str, country_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, country_id, filename, extension, is_default, created_at
            FROM resumes
            WHERE user_id = ? AND country_id = ?
            ORDER BY created_at ASC
            """,
            (user_id, country_id),
        ).fetchall()
    return [_row(row) for row in rows]


def get(user_id: str, resume_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, country_id, filename, extension, is_default, created_at
            FROM resumes
            WHERE user_id = ? AND id = ?
            """,
            (user_id, resume_id),
        ).fetchone()
    return _row(row) if row else None


def create(user_id: str, *, country_id: str, filename: str, extension: str, is_default: bool) -> dict:
    resume_id = new_id()
    created = now_iso()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO resumes (id, user_id, country_id, filename, extension, is_default, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (resume_id, user_id, country_id, filename, extension, 1 if is_default else 0, created),
        )
    return {
        "id": resume_id,
        "country_id": country_id,
        "filename": filename,
        "extension": extension,
        "is_default": is_default,
        "created_at": created,
    }


def set_default(user_id: str, country_id: str, resume_id: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE resumes SET is_default = 0 WHERE user_id = ? AND country_id = ?",
            (user_id, country_id),
        )
        conn.execute(
            "UPDATE resumes SET is_default = 1 WHERE user_id = ? AND id = ?",
            (user_id, resume_id),
        )


def delete(user_id: str, resume_id: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM resumes WHERE user_id = ? AND id = ?", (user_id, resume_id))
        conn.execute("UPDATE jobs SET resume_id = NULL WHERE user_id = ? AND resume_id = ?", (user_id, resume_id))


def clear_for_country(user_id: str, country_id: str) -> list[dict]:
    rows = list_for_country(user_id, country_id)
    if not rows:
        return []
    ids = [row["id"] for row in rows]
    with connect() as conn:
        conn.execute("DELETE FROM resumes WHERE user_id = ? AND country_id = ?", (user_id, country_id))
        conn.executemany(
            "UPDATE jobs SET resume_id = NULL WHERE user_id = ? AND resume_id = ?",
            [(user_id, resume_id) for resume_id in ids],
        )
    return rows
