#!/usr/bin/env python3
"""
Send a single email with a generated resume PDF attached. Used by generate_resume.py after each new PDF.
Standalone: no dependency on send_emails.py. Requires SMTP and optional Ollama env in .env.
"""

import logging
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

import requests

from email_sends_db import (
    TABLE_SEND_GENERATED_RESUME_EMAIL,
    duplicate_skip_reason,
    has_recent_application,
    init_db,
    is_dedup_enabled,
    is_logging_enabled,
    log_email_send,
)

BODY_MAX_CHARS = 2000

REQUIRED_ENV = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "FROM_EMAIL")
OPTIONAL_ENV = {
    "PROFILE_FILE": "profile.txt",
    "OLLAMA_BASE_URL": "http://localhost:11434",
    "OLLAMA_MODEL": "llama3.2",
}


def load_dotenv(path: str = ".env") -> None:
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    os.environ.setdefault(key, value)


def get_config() -> dict | None:
    load_dotenv()
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        return None
    return {
        "smtp_host": os.environ["SMTP_HOST"],
        "smtp_port": int(os.environ.get("SMTP_PORT", "587")),
        "smtp_user": os.environ["SMTP_USER"],
        "smtp_password": os.environ["SMTP_PASSWORD"],
        "from_email": os.environ["FROM_EMAIL"],
        "profile_file": os.environ.get("PROFILE_FILE", OPTIONAL_ENV["PROFILE_FILE"]),
        "ollama_base_url": os.environ.get("OLLAMA_BASE_URL", OPTIONAL_ENV["OLLAMA_BASE_URL"]).rstrip("/"),
        "ollama_model": os.environ.get("OLLAMA_MODEL", OPTIONAL_ENV["OLLAMA_MODEL"]),
    }


def load_profile(profile_file: str) -> str | None:
    path = Path(profile_file)
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8").strip()
    lines = [l for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]
    return "\n".join(lines).strip() or None


def parse_signature_from_profile(profile_text: str | None) -> dict:
    sig = {"name": "", "email": "", "phone": "", "portfolio": ""}
    if not profile_text:
        return sig
    for line in profile_text.splitlines():
        line = line.strip()
        if not line:
            continue
        lower = line.lower()
        if lower.startswith("name:"):
            sig["name"] = line.split(":", 1)[1].strip()
        elif lower.startswith("email:"):
            sig["email"] = line.split(":", 1)[1].strip()
        elif lower.startswith("phone") and ":" in line:
            sig["phone"] = line.split(":", 1)[1].strip()
        elif "portfolio" in lower or "portfilio" in lower:
            if ":" in line:
                sig["portfolio"] = line.split(":", 1)[1].strip()
    return sig


def format_signature(sig: dict) -> str:
    parts = []
    if sig.get("name"):
        parts.append(sig["name"])
    if sig.get("email"):
        parts.append(sig["email"])
    if sig.get("phone"):
        parts.append(sig["phone"])
    if sig.get("portfolio"):
        parts.append(sig["portfolio"])
    if not parts:
        return ""
    return "Best regards,\n\n" + "\n".join(parts)


def generate_body(
    company: str,
    role: str,
    name: str,
    job_description: str | None,
    profile_text: str | None,
    config: dict,
    logger: logging.Logger,
) -> str | None:
    url = f"{config['ollama_base_url']}/api/generate"
    is_cold_email = not (role or "").strip()
    is_anonymous_company = not (company or "").strip()
    has_jd = bool((job_description or "").strip())

    if is_anonymous_company:
        prompt = """Write a short, professional job application email body (2-4 sentences only).
- Addressed to the hiring team. Do not use or guess the company name; keep it anonymous. Refer to "your company", "your team", or "the company" (e.g. "your company's work", "the company's mission") so it feels personal without naming the company."""
    else:
        prompt = f"""Write a short, professional job application email body (2-4 sentences only).
- Addressed to the hiring team at {company}."""
    if is_cold_email:
        prompt += """
- This is a cold email (no specific role in the listing). Write as someone exploring opportunities, interested in the company, and open to relevant roles. Do not mention a specific job title.
- Professional tone, not robotic. No subject line. End with a sign-off like "Best regards". Do not include placeholders like [Your Name]. Keep it concise."""
    else:
        prompt += f"""
- Mention the company name and the role "{role}" naturally.
- Professional tone, not robotic. No subject line. End with a sign-off like "Best regards". Do not include placeholders like [Your Name]. Keep it concise."""
    if name and str(name).strip():
        prompt += f"\n- You may reference that you were referred by {name} if it fits naturally."

    if has_jd:
        prompt += f"""

Job description for this role:
{job_description.strip()[:3000]}

CRITICAL: Write the email based only on what in the candidate profile actually matches this job description. Mention only skills, experience, or projects from the profile that align with the JD. If something in the JD is not in the profile, do not claim it or imply the candidate has it. If there is little overlap, write a shorter, honest email that highlights only the matching parts; do not exaggerate or invent. Never lie."""

    if profile_text:
        role_instruction = (
            "This is a cold email (no specific role/JD): include all project details and key experience from the candidate profile so the recipient gets a full picture. You may use a few short paragraphs. Stay professional and concise."
            if is_cold_email and not has_jd
            else (
                'Use the job description above: mention only 1–2 items from the candidate profile that actually match the JD. Do not list everything; do not claim non-matching skills.'
                if has_jd
                else f'Based on the role "{role}", choose what to include: only 1–2 items that match (e.g. one relevant work experience OR one relevant project; for frontend highlight frontend work, for full-stack highlight full-stack, etc.). Do not list everything.'
            )
        )
        prompt += f"""

Use this candidate profile to personalize the email. {role_instruction}
- Do not add the candidate's name, email, phone or portfolio in the body—a signature block will be added automatically after your text.
Keep the email 2–4 sentences total.

Candidate profile:
{profile_text}"""
    payload = {"model": config["ollama_model"], "prompt": prompt, "stream": False}
    try:
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        body = (data.get("response") or "").strip()[:BODY_MAX_CHARS]
        return body or None
    except requests.RequestException as e:
        logger.exception("Ollama request failed: %s", e)
        return None


def _subject_for_send(company: str, role: str) -> str:
    has_role = (role or "").strip()
    has_company = (company or "").strip()
    if not has_role and not has_company:
        return "Reaching out"
    if not has_role:
        return f"Reaching out – {company}"
    if not has_company:
        return f"Application for {role}"
    return f"Application for {role} at {company}"


def _build_and_send(
    to_email: str,
    company: str,
    role: str,
    body: str,
    resume_path: str,
    config: dict,
    dry_run: bool,
    logger: logging.Logger,
) -> tuple[bool, str | None]:
    msg = EmailMessage()
    subject = _subject_for_send(company, role)
    msg["Subject"] = subject
    msg["From"] = config["from_email"]
    msg["To"] = to_email
    msg.set_content(body)
    with open(resume_path, "rb") as f:
        msg.add_attachment(f.read(), maintype="application", subtype="pdf", filename=Path(resume_path).name)
    if dry_run:
        logger.info("[DRY-RUN] Would send to %s (Company: %s, Role: %s)", to_email, company, role)
        return True, None
    try:
        if config["smtp_port"] == 465:
            with smtplib.SMTP_SSL(config["smtp_host"], config["smtp_port"]) as smtp:
                smtp.login(config["smtp_user"], config["smtp_password"])
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(config["smtp_host"], config["smtp_port"]) as smtp:
                smtp.starttls()
                smtp.login(config["smtp_user"], config["smtp_password"])
                smtp.send_message(msg)
        logger.info("Sent to %s (Company: %s, Role: %s)", to_email, company, role)
        return True, None
    except smtplib.SMTPException as e:
        logger.exception("SMTP failed for %s: %s", to_email, e)
        return False, str(e) or type(e).__name__


def send_email_for_row(
    row: dict,
    resume_path: str,
    logger: logging.Logger,
    dry_run: bool = False,
    region: str | None = None,
    excel_path: str | None = None,
    log_table: str = TABLE_SEND_GENERATED_RESUME_EMAIL,
) -> bool:
    """
    Send one email for the given row with the generated resume PDF attached.
    row must have Company, Role, Email; optional Name, Job Description.
    Returns True if sent (or dry-run), False on config/body/send failure.
    """
    if is_logging_enabled():
        init_db()

    to_email = str(row.get("Email", "")).strip()
    company = str(row.get("Company", "")).strip()
    role = str(row.get("Role", "")).strip()
    rp = Path(resume_path)
    pdf_path_str = str(rp.resolve()) if resume_path else None
    pdf_name = rp.name if resume_path else None
    subj = _subject_for_send(company, role)

    config = get_config()
    if not config:
        logger.error("SMTP not configured. Set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, FROM_EMAIL in .env")
        log_email_send(
            log_table,
            recipient_email=to_email or "",
            success=False,
            dry_run=dry_run,
            company=company or None,
            role=role or None,
            region=region,
            subject=subj,
            pdf_path=pdf_path_str,
            pdf_filename=pdf_name,
            excel_path=excel_path,
            failure_reason="no_config",
        )
        return False

    if not to_email or "@" not in to_email:
        logger.warning("Row has no valid Email; cannot send.")
        log_email_send(
            log_table,
            recipient_email=to_email or "",
            success=False,
            dry_run=dry_run,
            company=company or None,
            role=role or None,
            region=region,
            subject=subj,
            pdf_path=pdf_path_str,
            pdf_filename=pdf_name,
            excel_path=excel_path,
            failure_reason="invalid_email",
        )
        return False

    if is_dedup_enabled() and has_recent_application(to_email, company or None, role or None):
        logger.info(
            "Skipping %s (Company: %s, Role: %s): duplicate job/email within dedup window.",
            to_email,
            company,
            role,
        )
        log_email_send(
            log_table,
            recipient_email=to_email,
            success=False,
            dry_run=dry_run,
            company=company or None,
            role=role or None,
            region=region,
            subject=subj,
            pdf_path=pdf_path_str,
            pdf_filename=pdf_name,
            excel_path=excel_path,
            failure_reason=duplicate_skip_reason(),
        )
        return False

    name = row.get("Name")
    if name is None or (isinstance(name, float) and name != name):
        name = ""
    else:
        name = str(name).strip()
    jd = row.get("Job Description")
    if jd is None or (isinstance(jd, float) and jd != jd):
        job_description = None
    else:
        job_description = str(jd).strip() or None

    profile_text = load_profile(config["profile_file"])
    body = generate_body(company, role, name, job_description, profile_text, config, logger)
    if not body:
        logger.warning("No email body generated; skipping send.")
        log_email_send(
            log_table,
            recipient_email=to_email,
            success=False,
            dry_run=dry_run,
            company=company or None,
            role=role or None,
            region=region,
            subject=subj,
            pdf_path=pdf_path_str,
            pdf_filename=pdf_name,
            excel_path=excel_path,
            failure_reason="no_body_generated",
        )
        return False

    if profile_text:
        sig = parse_signature_from_profile(profile_text)
        signature_block = format_signature(sig)
        if signature_block:
            body = body + "\n\n" + signature_block

    ok, err = _build_and_send(to_email, company, role, body, resume_path, config, dry_run, logger)
    log_email_send(
        log_table,
        recipient_email=to_email,
        success=ok,
        dry_run=dry_run,
        company=company or None,
        role=role or None,
        region=region,
        subject=subj,
        pdf_path=pdf_path_str,
        pdf_filename=pdf_name,
        excel_path=excel_path,
        failure_reason=err,
    )
    return ok
