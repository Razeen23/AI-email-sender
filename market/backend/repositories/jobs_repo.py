from __future__ import annotations

from backend.clock import new_id, now_iso
from backend.db import connect


def list_for_user(user_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, company, role, contact_email, job_description, skills, country_id, resume_id, referral_name, created_at
            FROM jobs
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get(user_id: str, job_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, company, role, contact_email, job_description, skills, country_id, resume_id, referral_name, created_at
            FROM jobs
            WHERE user_id = ? AND id = ?
            """,
            (user_id, job_id),
        ).fetchone()
    return dict(row) if row else None


def create(
    user_id: str,
    *,
    company: str,
    role: str,
    contact_email: str,
    job_description: str,
    skills: str,
    country_id: str | None,
    resume_id: str | None,
    referral_name: str,
) -> dict:
    job_id = new_id()
    created = now_iso()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO jobs (
              id, user_id, company, role, contact_email, job_description, skills,
              country_id, resume_id, referral_name, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                user_id,
                company,
                role,
                contact_email,
                job_description,
                skills,
                country_id,
                resume_id,
                referral_name,
                created,
            ),
        )
    return {
        "id": job_id,
        "company": company,
        "role": role,
        "contact_email": contact_email,
        "job_description": job_description,
        "skills": skills,
        "country_id": country_id,
        "resume_id": resume_id,
        "referral_name": referral_name,
        "created_at": created,
    }


def set_resume(user_id: str, job_id: str, resume_id: str | None) -> bool:
    with connect() as conn:
        cursor = conn.execute(
            "UPDATE jobs SET resume_id = ? WHERE user_id = ? AND id = ?",
            (resume_id, user_id, job_id),
        )
    return cursor.rowcount > 0


def delete_all(user_id: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM jobs WHERE user_id = ?", (user_id,))


def delete(user_id: str, job_id: str) -> bool:
    with connect() as conn:
        cursor = conn.execute("DELETE FROM jobs WHERE user_id = ? AND id = ?", (user_id, job_id))
    return cursor.rowcount > 0
