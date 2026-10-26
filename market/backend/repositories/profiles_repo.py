from __future__ import annotations

import copy
import json

from backend.clock import now_iso
from backend.db import connect

EMPTY = {
    "name": "",
    "headline": "",
    "email": "",
    "phone": "",
    "city": "",
    "country": "",
    "linkedin": "",
    "github": "",
    "portfolio": "",
    "languages": [],
    "summary": "",
    "skills": [],
    "experience": [],
    "projects": [],
    "education": [],
    "certifications": [],
    "base_resume_filename": "",
}


def _load(row) -> dict:
    return {
        "name": row["name"],
        "headline": row["headline"],
        "email": row["email"],
        "phone": row["phone"],
        "city": row["city"],
        "country": row["country"],
        "linkedin": row["linkedin"],
        "github": row["github"],
        "portfolio": row["portfolio"],
        "languages": json.loads(row["languages_json"]),
        "summary": row["summary"],
        "skills": json.loads(row["skills_json"]),
        "experience": json.loads(row["experience_json"]),
        "projects": json.loads(row["projects_json"]),
        "education": json.loads(row["education_json"]),
        "certifications": json.loads(row["certifications_json"]),
        "base_resume_filename": row["base_resume_filename"],
    }


def get(user_id: str) -> dict:
    with connect() as conn:
        row = conn.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        return copy.deepcopy(EMPTY)
    return _load(row)


def save(user_id: str, profile: dict) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE profiles SET
              name = ?, headline = ?, email = ?, phone = ?, city = ?, country = ?,
              linkedin = ?, github = ?, portfolio = ?, languages_json = ?, summary = ?,
              skills_json = ?, experience_json = ?, projects_json = ?, education_json = ?,
              certifications_json = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (
                profile["name"],
                profile["headline"],
                profile["email"],
                profile["phone"],
                profile["city"],
                profile["country"],
                profile["linkedin"],
                profile["github"],
                profile["portfolio"],
                json.dumps(profile["languages"]),
                profile["summary"],
                json.dumps(profile["skills"]),
                json.dumps(profile["experience"]),
                json.dumps(profile["projects"]),
                json.dumps(profile["education"]),
                json.dumps(profile["certifications"]),
                now_iso(),
                user_id,
            ),
        )


def set_base_filename(user_id: str, filename: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE profiles SET base_resume_filename = ?, updated_at = ? WHERE user_id = ?",
            (filename, now_iso(), user_id),
        )
