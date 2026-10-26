from __future__ import annotations

from io import BytesIO

import pandas as pd

from backend.models.schemas import JobIn
from backend.repositories import countries_repo, jobs_repo, resumes_repo
from backend.services import country_service, resume_library_service
from backend.textutil import clip, norm_key, valid_email

COLUMN_ALIASES = {
    "company": "company",
    "company name": "company",
    "role": "role",
    "job title": "role",
    "title": "role",
    "hr email": "email",
    "email": "email",
    "contact email": "email",
    "contact": "email",
    "job description": "job_description",
    "description": "job_description",
    "jd": "job_description",
    "country": "country",
    "location": "country",
    "referral name": "referral",
    "referral": "referral",
    "referal name": "referral",
    "e-mail": "email",
    "email address": "email",
    "position": "role",
    "organisation": "company",
    "organization": "company",
    "skills": "skills",
    "skill": "skills",
    "required skills": "skills",
}


SHEET_HINT = (
    "The spreadsheet needs an email column. "
    "Suggested columns: email (required), role, company name, job description, skills, country, referral name. "
    "A blank role sends a cold email."
)


def _with_label(user_id: str, job: dict) -> dict:
    label = ""
    if job.get("country_id"):
        country = countries_repo.get(user_id, job["country_id"])
        label = country["label"] if country else ""
    filename = ""
    resume_id = job.get("resume_id")
    if resume_id:
        resume = resumes_repo.get(user_id, resume_id)
        if resume:
            filename = resume["filename"]
        else:
            job["resume_id"] = None
    job["country_label"] = label
    job["resume_filename"] = filename
    job["skills"] = job.get("skills") or ""
    return job


def list_jobs(user_id: str) -> list[dict]:
    return [_with_label(user_id, job) for job in jobs_repo.list_for_user(user_id)]


def _country_or_none(user_id: str, country_id: str | None) -> str | None:
    if not country_id:
        return None
    country_service.require(user_id, country_id)
    return country_id


def create(user_id: str, body: JobIn) -> dict:
    email = clip(body.contact_email, 254)
    if not valid_email(email):
        raise ValueError("Enter a valid contact email for this job.")
    country_id = _country_or_none(user_id, (body.country_id or "").strip() or None)
    job = jobs_repo.create(
        user_id,
        company=clip(body.company, 160),
        role=clip(body.role, 160),
        contact_email=email,
        job_description=clip(body.job_description, 12000),
        skills=clip(body.skills, 2000),
        country_id=country_id,
        resume_id=resume_library_service.default_resume_id(user_id, country_id),
        referral_name=clip(body.referral_name, 120),
    )
    return _with_label(user_id, job)


def assign_resume(user_id: str, job_id: str, resume_id: str) -> dict:
    job = jobs_repo.get(user_id, job_id)
    if not job:
        raise ValueError("That job is not on your list.")
    resume = resumes_repo.get(user_id, resume_id)
    if not resume:
        raise ValueError("That resume is not on your account.")
    if job.get("country_id") and resume["country_id"] != job["country_id"]:
        raise ValueError("Choose a resume from this job's country.")
    if not jobs_repo.set_resume(user_id, job_id, resume_id):
        raise ValueError("That job is not on your list.")
    updated = jobs_repo.get(user_id, job_id)
    if not updated:
        raise ValueError("That job is not on your list.")
    return _with_label(user_id, updated)


def delete(user_id: str, job_id: str) -> None:
    if not jobs_repo.delete(user_id, job_id):
        raise ValueError("That job is not on your list.")


def _cell(row: dict, key: str) -> str:
    value = row.get(key, "")
    if value is None:
        return ""
    return str(value).strip()


def _match_country(countries: list[dict], label: str, default_id: str | None) -> str | None:
    if label:
        key = norm_key(label)
        for country in countries:
            if norm_key(country["label"]) == key:
                return country["id"]
    return default_id


def _read_table(filename: str, content: bytes) -> pd.DataFrame:
    lower = filename.lower()
    if lower.endswith(".csv"):
        return pd.read_csv(BytesIO(content))
    if not lower.endswith(".xlsx"):
        raise ValueError("Upload a .xlsx or .csv file.")
    sheet: str | int = 0
    try:
        from openpyxl import load_workbook

        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
        if workbook.active is not None and workbook.active.title:
            sheet = workbook.active.title
        workbook.close()
    except Exception:
        sheet = 0
    return pd.read_excel(BytesIO(content), sheet_name=sheet)


def _this_file_columns(frame: pd.DataFrame) -> pd.DataFrame:
    kept = []
    seen = set()
    for column in frame.columns:
        name = str(column).strip()
        key = norm_key(name)
        if not name or key.startswith("unnamed") or key in seen:
            continue
        seen.add(key)
        kept.append(column)
    if not kept:
        return frame.iloc[:, 0:0]
    return frame.loc[:, kept]


def import_spreadsheet(user_id: str, filename: str, content: bytes, default_country_id: str) -> dict:
    if len(content) > 2_000_000:
        raise ValueError("Spreadsheet must be under 2 MB.")
    try:
        frame = _read_table(filename, content)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Could not read that spreadsheet.") from exc
    frame = _this_file_columns(frame.fillna(""))
    columns = [str(column).strip() for column in frame.columns]
    renamed = {}
    used_targets = set()
    for column in frame.columns:
        target = COLUMN_ALIASES.get(norm_key(str(column)))
        if target and target not in used_targets:
            renamed[column] = target
            used_targets.add(target)
    frame = frame.rename(columns=renamed)
    if "email" not in frame.columns:
        raise ValueError(SHEET_HINT)
    default_id = _country_or_none(user_id, default_country_id.strip() or None)
    countries = countries_repo.list_for_user(user_id)
    created_jobs: list[dict] = []
    skipped: list[str] = []
    records = frame.to_dict(orient="records")
    if len(records) > 500:
        raise ValueError("Upload 500 rows or fewer.")
    jobs_repo.delete_all(user_id)
    for index, record in enumerate(records, start=2):
        company = clip(_cell(record, "company"), 160)
        role = clip(_cell(record, "role"), 160)
        email = clip(_cell(record, "email"), 254)
        if not company and not role and not email and not _cell(record, "job_description"):
            continue
        if not valid_email(email):
            skipped.append(f"Row {index}: email is missing or invalid.")
            continue
        country_id = _match_country(countries, _cell(record, "country"), default_id)
        job = jobs_repo.create(
            user_id,
            company=company,
            role=role,
            contact_email=email,
            job_description=clip(_cell(record, "job_description"), 12000),
            skills=clip(_cell(record, "skills"), 2000),
            country_id=country_id,
            resume_id=resume_library_service.default_resume_id(user_id, country_id),
            referral_name=clip(_cell(record, "referral"), 120),
        )
        created_jobs.append(_with_label(user_id, job))
    return {"created": len(created_jobs), "skipped": skipped[:50], "jobs": created_jobs, "columns": columns}
