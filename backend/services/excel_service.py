from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from backend.paths import EXCEL_DIRS, infer_region_from_path, resolve_excel_path, to_rel
from backend.services.config_service import get_send_config
from email_sends_db import has_recent_application
from cold_email import ensure_role_column, is_cold_email
from resume_selection import get_resume_path
from send_emails2 import _normalize_cell, normalize_columns

logger = logging.getLogger("backend.excel")


def list_excel_files() -> list[dict]:
    files: list[dict] = []
    for region, folder in EXCEL_DIRS.items():
        if not folder.is_dir():
            continue
        for path in sorted(folder.iterdir()):
            if path.name.startswith("~$") or path.name.startswith("."):
                continue
            if path.suffix.lower() not in {".xlsx", ".xls"}:
                continue
            stat = path.stat()
            files.append(
                {
                    "path": to_rel(path),
                    "name": path.name,
                    "region": region,
                    "size": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                }
            )
    files.sort(key=lambda item: item["modified_at"], reverse=True)
    return files


def _safe_filename(name: str) -> str:
    base = Path(name).name
    base = re.sub(r"[^\w.\- ]+", "_", base).strip()
    if not base.lower().endswith((".xlsx", ".xls")):
        raise ValueError("Upload must be an Excel file (.xlsx or .xls).")
    return base or "upload.xlsx"


def save_upload(filename: str, data: bytes, region: str) -> dict:
    region = (region or "").strip().upper()
    if region not in EXCEL_DIRS:
        raise ValueError("Region must be INR or UAE.")
    folder = EXCEL_DIRS[region]
    folder.mkdir(parents=True, exist_ok=True)
    safe = _safe_filename(filename)
    dest = folder / safe
    if dest.exists():
        stem, suffix = dest.stem, dest.suffix
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        dest = folder / f"{stem}_{stamp}{suffix}"
    dest.write_bytes(data)
    stat = dest.stat()
    return {
        "path": to_rel(dest),
        "name": dest.name,
        "region": region,
        "size": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
    }


def _optional_cell(row: dict, key: str) -> str | None:
    value = _normalize_cell(row.get(key, ""))
    return value or None


def preview_excel(rel_path: str, region: str | None = None) -> dict:
    path = resolve_excel_path(rel_path)
    resolved_region = infer_region_from_path(path, region)
    df = pd.read_excel(path, engine="openpyxl")
    df = ensure_role_column(normalize_columns(df))
    required = {"Company", "Email"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Excel missing columns after mapping: {', '.join(sorted(missing))}. Company and HR email are required. Role is optional."
        )

    config = get_send_config()
    records = df.to_dict("records")
    rows: list[dict] = []
    invalid = 0
    applied = 0
    for index, row in enumerate(records):
        email = str(row.get("Email", "") or "").strip()
        valid_email = bool(email) and "@" in email and email.lower() != "nan"
        if not valid_email:
            invalid += 1
        company = _normalize_cell(row.get("Company", ""))
        role = _normalize_cell(row.get("Role", ""))
        job_description = _optional_cell(row, "Job Description")
        key_skills = _optional_cell(row, "Key Skills")
        why_match = _optional_cell(row, "Why Match")
        resume_abs = get_resume_path(
            config["resumes_base"],
            resolved_region,
            role,
            logger,
            job_description=job_description,
            key_skills=key_skills,
            why_match=why_match,
        )
        resume_path = None
        resume_filename = None
        if resume_abs:
            resume_file = Path(resume_abs)
            resume_path = to_rel(resume_file)
            resume_filename = resume_file.name
        already = bool(valid_email and has_recent_application(email, company or None, role or None))
        if already:
            applied += 1
        rows.append(
            {
                "index": index,
                "company": company,
                "role": role,
                "cold_email": is_cold_email(role),
                "email": email,
                "job_description": job_description,
                "key_skills": key_skills,
                "why_match": why_match,
                "referral_name": _optional_cell(row, "Name"),
                "valid_email": valid_email,
                "resume_path": resume_path,
                "resume_filename": resume_filename,
                "already_applied": already,
            }
        )
    return {
        "path": to_rel(path),
        "region": resolved_region,
        "total_rows": len(rows),
        "invalid_email_count": invalid,
        "already_applied_count": applied,
        "rows": rows,
    }


def load_send_rows(rel_path: str, region: str | None = None) -> tuple[str, list[dict]]:
    preview = preview_excel(rel_path, region)
    return preview["region"], preview["rows"]
