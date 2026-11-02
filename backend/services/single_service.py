from __future__ import annotations

import logging
import re
from pathlib import Path

from backend.paths import resolve_resume_path, to_rel
from backend.services.config_service import get_send_config, smtp_configured
from backend.services.send_service import _clean_body
from email_sends_db import (
    TABLE_SEND_EMAILS2,
    has_recent_application,
    init_db,
    is_logging_enabled,
    log_email_send,
)
from cold_email import is_cold_email
from resume_selection import suggest_resume_path
from send_emails2 import _ollama_body, build_and_send, generate_body, get_subject, load_profile

logger = logging.getLogger("backend.single")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_STRUCTURE = """Follow this structure in order:
1. Greeting
2. About me and the role I am applying for
3. About my achievements and experience (1–2 strongest, relevant points)
4. How I can add value in their company
Do not add any contact details (no name/email/phone/portfolio/links), do not include any URLs (including job links), and do not add "Signature", "Best regards", "Sincerely", or any sign-off—only the main email content. A full signature block is added automatically; do not duplicate it.
Do not write "Subject:", "Email subject:", or any email header line—the subject is set separately; start directly with the greeting (e.g. Dear Hiring Team)."""


def normalize_region(region: str) -> str:
    key = (region or "").strip().upper()
    if key in {"INR", "INDIA", "IN"}:
        return "INR"
    if key in {"UAE", "UNITED ARAB EMIRATES"}:
        return "UAE"
    raise ValueError("Country must be India or UAE.")


def _valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match((email or "").strip()))


def _kind(role: str, skills: str, job_description: str) -> str:
    if is_cold_email(role) and not skills.strip() and not job_description.strip():
        return "cold"
    return "application"


def suggest_single(
    *,
    email: str = "",
    role: str = "",
    skills: str = "",
    job_description: str = "",
    region: str,
) -> dict:
    resolved = normalize_region(region)
    config = get_send_config()
    resume_abs = suggest_resume_path(
        config["resumes_base"],
        resolved,
        role,
        logger,
        job_description=job_description or None,
        key_skills=skills or None,
    )
    resume_path = None
    resume_filename = None
    if resume_abs:
        resume_file = Path(resume_abs)
        resume_path = to_rel(resume_file)
        resume_filename = resume_file.name
    recipient = email.strip()
    already = bool(
        _valid_email(recipient)
        and has_recent_application(recipient, None, role.strip() or None)
    )
    return {
        "region": resolved,
        "kind": _kind(role, skills, job_description),
        "resume_path": resume_path,
        "resume_filename": resume_filename,
        "already_applied": already,
    }


def _draft_from_listing(
    *,
    skills: str,
    job_description: str,
    profile_text: str | None,
    config: dict,
) -> str | None:
    prompt = f"""Write a short, professional job application email body.
- Addressed to the hiring team. Do not use or guess the company name. Say "your team" or "the company".
- There is no job title. Do not invent one.
{_STRUCTURE}
- Professional tone, not robotic. Start with the greeting. Keep it concise."""
    if skills.strip():
        prompt += f"""

Key skills from the listing (context, not guaranteed requirements):
{skills.strip()[:1500]}"""
    if job_description.strip():
        prompt += f"""

Job description:
{job_description.strip()[:3000]}

CRITICAL: Write the email based only on what in the candidate profile actually matches this job description and the key skills above. Mention only skills, experience, or projects from the profile that align. If something is not in the profile, do not claim it."""
    else:
        prompt += """

CRITICAL: Keep the email honest and broadly relevant without inventing experience."""
    if profile_text:
        prompt += f"""

Use this candidate profile to personalize the email. Choose only 1–2 matching items. Do not add a sign-off or contact details.

Candidate profile:
{profile_text}"""
    url = f"{config['ollama_base_url']}/api/generate"
    return _ollama_body(url, prompt, "", "", "", config, logger, {})


def draft_single(
    *,
    email: str = "",
    role: str = "",
    skills: str = "",
    job_description: str = "",
    region: str,
) -> dict:
    resolved = normalize_region(region)
    config = get_send_config()
    profile_text = load_profile(config, logger)
    role_clean = role.strip()
    skills_clean = skills.strip()
    jd_clean = job_description.strip()
    kind = _kind(role_clean, skills_clean, jd_clean)
    if kind == "cold":
        body = generate_body("", role_clean, None, None, None, profile_text, config, logger, {})
        subject = get_subject("", role_clean)
    elif is_cold_email(role_clean):
        body = _draft_from_listing(
            skills=skills_clean,
            job_description=jd_clean,
            profile_text=profile_text,
            config=config,
        )
        subject = "Application"
    else:
        body = generate_body(
            "",
            role_clean,
            jd_clean or None,
            skills_clean or None,
            None,
            profile_text,
            config,
            logger,
            {},
        )
        subject = get_subject("", role_clean)
    if not body or not body.strip():
        raise RuntimeError("Could not write the email. Check that Ollama is running.")
    recipient = email.strip()
    already = bool(
        _valid_email(recipient)
        and has_recent_application(recipient, None, role_clean or None)
    )
    return {
        "region": resolved,
        "kind": kind,
        "subject": subject,
        "body": _clean_body(body, resolved),
        "already_applied": already,
    }


def send_single(
    *,
    email: str,
    role: str = "",
    skills: str = "",
    job_description: str = "",
    region: str,
    resume_path: str,
    subject: str,
    body: str,
    dry_run: bool = True,
) -> dict:
    del skills, job_description
    if not dry_run and not smtp_configured():
        raise ValueError("SMTP is not configured. Add credentials to .env or use dry-run.")
    recipient = email.strip()
    if not _valid_email(recipient):
        raise ValueError("Enter a valid email address.")
    resolved = normalize_region(region)
    subject_clean = subject.strip()
    body_clean = body.strip()
    if not subject_clean or not body_clean:
        raise ValueError("Write the email before sending.")
    resume_file = resolve_resume_path(resume_path)
    config = get_send_config()
    if is_logging_enabled():
        init_db()
    role_clean = role.strip()
    ok, err = build_and_send(
        recipient,
        "",
        role_clean,
        body_clean,
        str(resume_file),
        config,
        dry_run,
        logger,
        subject=subject_clean,
    )
    log_email_send(
        TABLE_SEND_EMAILS2,
        recipient_email=recipient,
        success=ok,
        dry_run=dry_run,
        company=None,
        role=role_clean or None,
        region=resolved,
        subject=subject_clean,
        pdf_path=str(resume_file.resolve()),
        pdf_filename=resume_file.name,
        excel_path="single",
        failure_reason=err,
    )
    if not ok:
        raise RuntimeError(err or "Could not send the email.")
    return {
        "ok": True,
        "dry_run": dry_run,
        "email": recipient,
        "subject": subject_clean,
        "region": resolved,
        "resume_path": to_rel(resume_file),
        "resume_filename": resume_file.name,
    }
