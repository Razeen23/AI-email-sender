from __future__ import annotations

from backend.clock import new_id, now_iso, today_start_iso
from backend.db import connect
from backend.textutil import norm_key


def record(
    user_id: str,
    *,
    job_id: str | None,
    company: str,
    role: str,
    contact_email: str,
    country_label: str,
    status: str,
    subject: str,
    body: str,
    resume_filename: str,
    error: str,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO sends (
              id, user_id, job_id, company, role, contact_email, company_key, role_key, email_key,
              country_label, status, subject, body, resume_filename, error, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id(),
                user_id,
                job_id,
                company,
                role,
                contact_email,
                norm_key(company),
                norm_key(role),
                norm_key(contact_email),
                country_label,
                status,
                subject,
                body,
                resume_filename,
                error[:500],
                now_iso(),
            ),
        )


def already_sent(user_id: str, company: str, role: str, contact_email: str) -> bool:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM sends
            WHERE user_id = ? AND company_key = ? AND role_key = ? AND email_key = ? AND status = 'sent'
            LIMIT 1
            """,
            (user_id, norm_key(company), norm_key(role), norm_key(contact_email)),
        ).fetchone()
    return row is not None


def count_sent_today(user_id: str) -> int:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n FROM sends
            WHERE user_id = ? AND status = 'sent' AND created_at >= ?
            """,
            (user_id, today_start_iso()),
        ).fetchone()
    return int(row["n"])


def status_counts(user_id: str) -> dict[str, int]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM sends WHERE user_id = ? GROUP BY status",
            (user_id,),
        ).fetchall()
    return {row["status"]: int(row["n"]) for row in rows}


def sent_by_country(user_id: str) -> dict[str, int]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT country_label, COUNT(*) AS n FROM sends
            WHERE user_id = ? AND status = 'sent'
            GROUP BY country_label
            ORDER BY n DESC
            """,
            (user_id,),
        ).fetchall()
    return {(row["country_label"] or "Unset"): int(row["n"]) for row in rows}


def list_for_user(user_id: str, limit: int = 100) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, company, role, contact_email, country_label, status, subject, body,
                   error, resume_filename, created_at
            FROM sends
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]
