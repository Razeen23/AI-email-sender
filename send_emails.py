#!/usr/bin/env python3
"""
AI Email Sender: Read Excel (INR/UAE), pick resume by role, generate body via Ollama, send via SMTP.

Resume location is driven by the Excel file:
- inr_companies_test.xlsx (or path containing "inr") → resumes from resumes/INR (folder + PDF chosen by role)
- uae_companies_test.xlsx (or path containing "uae") → resumes from resumes/UAE (folder + PDF chosen by role)

Usage: python send_emails.py inr_companies_test.xlsx [--region inr|uae] [--dry-run]
"""

import argparse
import logging
import os
import re
import smtplib
import sys
import time
from email.message import EmailMessage
from pathlib import Path

import pandas as pd
import requests

from email_sends_db import (
    TABLE_SEND_EMAILS,
    duplicate_skip_reason,
    has_recent_application,
    init_db,
    is_dedup_enabled,
    is_logging_enabled,
    log_email_send,
)
from fallback_email_body import build_fallback_application_body
from resume_selection import get_resume_path


# --- .env loading (no external lib) ---
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


# --- Config ---
REQUIRED_ENV = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "FROM_EMAIL")
OPTIONAL_ENV = {
    "RESUMES_BASE": "resumes",
    "PROFILE_FILE": "profile.txt",
    "OLLAMA_BASE_URL": "http://localhost:11434",
    "OLLAMA_MODEL": "llama3.2",
}
DELAY_SECONDS = 10
BODY_MAX_CHARS = 2000


def get_config():
    load_dotenv()
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        sys.exit(f"Missing required env vars: {', '.join(missing)}. Set them or add to .env")
    config = {
        "smtp_host": os.environ["SMTP_HOST"],
        "smtp_port": int(os.environ.get("SMTP_PORT", "587")),
        "smtp_user": os.environ["SMTP_USER"],
        "smtp_password": os.environ["SMTP_PASSWORD"],
        "from_email": os.environ["FROM_EMAIL"],
        "resumes_base": os.environ.get("RESUMES_BASE", OPTIONAL_ENV["RESUMES_BASE"]),
        "profile_file": os.environ.get("PROFILE_FILE", OPTIONAL_ENV["PROFILE_FILE"]),
        "ollama_base_url": os.environ.get("OLLAMA_BASE_URL", OPTIONAL_ENV["OLLAMA_BASE_URL"]).rstrip("/"),
        "ollama_model": os.environ.get("OLLAMA_MODEL", OPTIONAL_ENV["OLLAMA_MODEL"]),
    }
    return config


def infer_region(excel_path: str, region_arg: str | None) -> str:
    """Infer region from --region or Excel location/name.

    Priority:
    1) Folder-based: .../INR_Excel/<file>.xlsx -> INR, .../UAE_Excel/<file>.xlsx -> UAE
    2) Filename-based fallback: name containing "inr" or "uae"
    """
    if region_arg:
        r = region_arg.strip().upper()
        if r in ("INR", "UAE"):
            return r
        sys.exit(f"Invalid --region: use 'inr' or 'uae'")
    p = Path(excel_path)
    parts_lower = [part.lower() for part in p.parts]
    if "inr_excel" in parts_lower:
        return "INR"
    if "uae_excel" in parts_lower:
        return "UAE"

    path_lower = p.name.lower()
    if "inr" in path_lower:
        return "INR"
    if "uae" in path_lower:
        return "UAE"
    sys.exit(
        "Could not infer region from Excel path. Put the Excel in INR_Excel/ or UAE_Excel/, or use --region inr|uae."
    )


def setup_logging(dry_run: bool) -> logging.Logger:
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    run_type = "dryrun" if dry_run else "run"
    log_file = log_dir / f"email_sender_{run_type}_{timestamp}.log"
    logger = logging.getLogger("email_sender")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh.setFormatter(fmt)
    ch.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    col_map = {}
    for c in df.columns:
        key = str(c).strip().lower()
        if "company" in key and "name" in key:
            col_map[c] = "Company"
        elif key == "role":
            col_map[c] = "Role"
        elif "hr" in key and "email" in key:
            col_map[c] = "Email"
        elif "referal" in key or "referral" in key:
            col_map[c] = "Name"
        elif ("job" in key and "description" in key) or key == "jd":
            col_map[c] = "Job Description"
    df = df.rename(columns=col_map)
    return df


def load_excel(excel_path: str, logger: logging.Logger) -> pd.DataFrame:
    if not os.path.isfile(excel_path):
        sys.exit(f"Excel file not found: {excel_path}")
    df = pd.read_excel(excel_path, engine="openpyxl")
    df = normalize_columns(df)
    required = {"Company", "Role", "Email"}
    missing = required - set(df.columns)
    if missing:
        sys.exit(f"Excel missing columns (after mapping): {missing}. Expected company name, role, HR email.")
    before = len(df)
    df = df.dropna(subset=["Email"])
    df = df[df["Email"].astype(str).str.contains("@", na=False)]
    dropped = before - len(df)
    if dropped:
        logger.warning("Dropped %d rows with missing or invalid Email.", dropped)
    return df


def _normalize_cell(val) -> str:
    """Treat empty and pandas 'nan' string as empty; return stripped string."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    s = str(val).strip()
    return "" if s.lower() == "nan" or not s else s


def get_subject(company: str, role: str) -> str:
    """Return email subject from company and role (cold email / anonymous company handled)."""
    has_role = _normalize_cell(role)
    has_company = _normalize_cell(company)
    if not has_role and not has_company:
        return "Reaching out"
    if not has_role:
        return f"Reaching out – {company}"
    if not has_company:
        return f"Application for {role}"
    return f"Application for {role} at {company}"


def load_profile(config: dict, logger: logging.Logger) -> str | None:
    """Load candidate profile from TXT file (email, name, phone, work exp, projects). Returns None if missing."""
    path = Path(config["profile_file"])
    if not path.is_file():
        logger.debug("No profile file at %s; emails will not include your personal info.", path)
        return None
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read().strip()
        # Drop comment lines so they are not sent to the model
        lines = [l for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]
        return "\n".join(lines).strip() or None
    except OSError as e:
        logger.warning("Could not read profile file %s: %s", path, e)
        return None


# Region-based fixed signature blocks for all sent emails (do not include in generated body)
DEFAULT_SIGNATURE_UAE = """Best regards,

Razeen H
razeen.official23@gmail.com
+971 50 769 7208
https://razeen-portfolio.vercel.app"""

DEFAULT_SIGNATURE_INR = """Best regards,

Razeen H
razeen.official23@gmail.com
+91 93450 35514
https://razeen-portfolio.vercel.app"""


def get_signature_block(region: str) -> str:
    """Return the signature block to append based on region (UAE vs INR)."""
    return DEFAULT_SIGNATURE_UAE if (region or "").strip().upper() == "UAE" else DEFAULT_SIGNATURE_INR


# Trailing lines to strip from generated body so we only have one sign-off (our block)
_SIGN_OFF_PATTERNS = (
    "signature",
    "best regards",
    "sincerely",
    "kind regards",
    "thanks",
    "thank you",
    "regards",
)


def _is_sign_off_line(line: str) -> bool:
    s = line.strip().lower().rstrip(".,:")
    if not s:
        return True
    if s in _SIGN_OFF_PATTERNS:
        return True
    if s.startswith("signature") or s == "sign off":
        return True
    return False


def strip_trailing_sign_off(body: str) -> str:
    """Remove trailing 'Signature', 'Best regards', etc. so only our appended signature block remains."""
    if not (body or "").strip():
        return body or ""
    lines = body.rstrip().split("\n")
    while lines and _is_sign_off_line(lines[-1]):
        lines.pop()
    return "\n".join(lines).rstrip()


_SUBJECT_HEADER_LINE_RE = re.compile(
    r"^(?:\*\*)?(?:subject|email\s*subject|subject\s*line)(?:\*\*)?\s*:.*$",
    re.I,
)


def strip_leading_subject_line(body: str) -> str:
    """Remove Subject: lines the model sometimes prepends (the real subject is set on the email, not in the body)."""
    if not (body or "").strip():
        return body or ""
    lines = body.split("\n")
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped:
            i += 1
            continue
        if _SUBJECT_HEADER_LINE_RE.match(stripped):
            i += 1
            continue
        break
    return "\n".join(lines[i:]).lstrip()


_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
_URL_RE = re.compile(r"https?://\S+", re.I)
_PHONE_RE = re.compile(r"(\+\d[\d\s-]{6,}\d)")


def strip_trailing_contact_block(body: str) -> str:
    """Remove trailing contact details (name/email/phone/portfolio) that the model may output."""
    if not (body or "").strip():
        return body or ""
    lines = body.rstrip().split("\n")
    while lines:
        last_raw = lines[-1]
        last = last_raw.strip()
        if not last:
            lines.pop()
            continue
        last_lower = last.lower()

        is_contact = False
        if last_lower in {"razeen h"}:
            is_contact = True
        if _EMAIL_RE.search(last):
            is_contact = True
        if _PHONE_RE.search(last):
            is_contact = True
        if _URL_RE.search(last) and ("portfolio" in last_lower or "vercel.app" in last_lower):
            is_contact = True

        if is_contact:
            lines.pop()
            continue
        break
    return "\n".join(lines).rstrip()


def generate_body(
    company: str,
    role: str,
    name: str,
    job_description: str | None,
    profile_text: str | None,
    config: dict,
    logger: logging.Logger,
    ollama_state: dict | None = None,
) -> str | None:
    url = f"{config['ollama_base_url']}/api/generate"
    role_clean = _normalize_cell(role)
    company_clean = _normalize_cell(company)
    is_cold_email = not role_clean
    is_anonymous_company = not company_clean
    has_jd = bool((job_description or "").strip())

    # Email structure: greeting → about me + role (if any) → achievements/exp → how I add value. Signature is added automatically.
    structure = """Follow this structure in order:
1. Greeting
2. About me and the role I am applying for (if a role is mentioned; otherwise about me and my interest)
3. About my achievements and experience
4. How I can add value in their company
Do not add any contact details (no name/email/phone/portfolio/links) and do not add "Signature", "Best regards", "Sincerely", or any sign-off—only the main email content. A full signature block is added automatically; do not duplicate it.
Do not write "Subject:", "Email subject:", or any email header line—the subject is set separately; start directly with the greeting (e.g. Dear Hiring Team)."""
    if is_anonymous_company:
        prompt = f"""Write a short, professional job application email body.
- Addressed to the hiring team. Do not use or guess the company name; keep it anonymous. Refer to "your company", "your team", or "the company" (e.g. "your company's work", "the company's mission") so it feels personal without naming the company.
{structure}"""
    else:
        prompt = f"""Write a short, professional job application email body.
- Addressed to the hiring team at {company_clean}.
{structure}"""
    if is_cold_email:
        prompt += """
- This is a cold email (no specific role in the listing). Write as a developer with 2+ years of experience looking for an opportunity in development roles. Do not mention a specific job title. Never use the word "nan" or any placeholder for a role.
- Professional tone, not robotic. Do not write "Subject:" or any email header; start with the greeting. Keep it concise."""
    else:
        prompt += f"""
- Mention the company name and the role "{role_clean}" naturally.
- Professional tone, not robotic. Do not write "Subject:" or any email header; start with the greeting. Keep it concise."""
    if name:
        prompt += f"\n- You may reference that you were referred by {name} if it fits naturally."
    else:
        prompt += "\n- Do not mention being referred by anyone; do not add any referral phrase (e.g. no 'I was referred to you by...')."

    # Job description: tailor email to JD but only use matching content—never lie
    if has_jd:
        prompt += f"""

Job description for this role:
{job_description.strip()[:3000]}

CRITICAL: Write the email based only on what in the candidate profile actually matches this job description. Mention only skills, experience, or projects from the profile that align with the JD. If something in the JD is not in the profile, do not claim it or imply the candidate has it. If there is little overlap, write a shorter, honest email that highlights only the matching parts; do not exaggerate or invent. Never lie."""

    if profile_text:
        role_instruction = (
            "This is a cold email so highlight 1–2 broadly relevant experiences or projects (full-stack, frontend, or general dev)."
            if is_cold_email and not has_jd
            else (
                f'Use the job description above: mention only 1–2 items from the candidate profile that actually match the JD. Do not list everything; do not claim non-matching skills.'
                if has_jd
                else f'Based on the role "{role_clean}", choose what to include: only 1–2 items that match (e.g. one relevant work experience OR one relevant project; for frontend highlight frontend work, for full-stack highlight full-stack, etc.). Do not list everything.'
            )
        )
        prompt += f"""

Use this candidate profile to personalize the email. {role_instruction}
- Do not add "Signature", "Best regards", or any sign-off in the body—a full signature block is added automatically.
- Keep the email concise (roughly 2–4 short paragraphs matching the structure above).

Candidate profile:
{profile_text}"""
    payload = {"model": config["ollama_model"], "prompt": prompt, "stream": False}
    try:
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        body = (data.get("response") or "").strip()[:BODY_MAX_CHARS]
        if body:
            return body
        if ollama_state is not None and not ollama_state.get("empty_body_warned"):
            logger.warning("Ollama returned an empty body; using template email body.")
            ollama_state["empty_body_warned"] = True
        return build_fallback_application_body(company, role, name, max_chars=BODY_MAX_CHARS)
    except requests.RequestException as e:
        if ollama_state is not None and not ollama_state.get("ollama_unreachable_warned"):
            logger.warning("Ollama request failed (%s); using template email body.", e)
            ollama_state["ollama_unreachable_warned"] = True
        return build_fallback_application_body(company, role, name, max_chars=BODY_MAX_CHARS)


def build_and_send(
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
    msg["Subject"] = get_subject(company, role)
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Send personalized job emails from Excel using Ollama and SMTP.")
    parser.add_argument("excel_path", help="Path to Excel file (e.g. inr_companies_test.xlsx or uae_companies_test.xlsx)")
    parser.add_argument("--region", choices=["inr", "uae"], help="Force region (default: inferred from filename)")
    parser.add_argument("--dry-run", action="store_true", help="Generate and log only; do not send email")
    args = parser.parse_args()

    config = get_config()
    region = infer_region(args.excel_path, args.region)
    logger = setup_logging(args.dry_run)
    if is_logging_enabled():
        init_db()

    logger.info(
        "Starting email sender: excel=%s region=%s dry_run=%s ollama=%s",
        args.excel_path,
        region,
        args.dry_run,
        config["ollama_base_url"],
    )
    resumes_base = Path(config["resumes_base"])
    region_dir = resumes_base / region
    if not region_dir.is_dir():
        sys.exit(f"Resumes region directory not found: {region_dir}")

    df = load_excel(args.excel_path, logger)
    rows = list(df.to_dict("records"))
    total = len(rows)
    logger.info("Loaded %d recipients from Excel.", total)

    profile_text = load_profile(config, logger)
    if profile_text:
        logger.info("Loaded profile from %s.", config["profile_file"])

    ollama_state: dict = {}

    for i, row in enumerate(rows):
        company = _normalize_cell(row.get("Company", ""))
        role = _normalize_cell(row.get("Role", ""))
        to_email = str(row.get("Email", "")).strip()
        name = _normalize_cell(row.get("Name", ""))  # referral name; empty/nan = do not mention referral
        job_description = row.get("Job Description")
        if job_description is None or pd.isna(job_description):
            job_description = None
        else:
            job_description = str(job_description).strip() or None

        resume_path = get_resume_path(
            config["resumes_base"],
            region,
            role,
            logger,
            job_description=job_description,
        )
        if not resume_path:
            log_email_send(
                TABLE_SEND_EMAILS,
                recipient_email=to_email,
                success=False,
                dry_run=args.dry_run,
                company=company or None,
                role=role or None,
                region=region,
                subject=get_subject(company, role),
                excel_path=args.excel_path,
                failure_reason="no_resume",
            )
            continue

        if is_dedup_enabled() and has_recent_application(to_email, company or None, role or None):
            logger.info(
                "Skipping %s (Company: %s, Role: %s): duplicate job/email within dedup window.",
                to_email,
                company,
                role,
            )
            rp = Path(resume_path)
            log_email_send(
                TABLE_SEND_EMAILS,
                recipient_email=to_email,
                success=False,
                dry_run=args.dry_run,
                company=company or None,
                role=role or None,
                region=region,
                subject=get_subject(company, role),
                pdf_path=str(rp.resolve()),
                pdf_filename=rp.name,
                excel_path=args.excel_path,
                failure_reason=duplicate_skip_reason(),
            )
            continue

        body = generate_body(
            company, role, name, job_description, profile_text, config, logger, ollama_state=ollama_state
        )
        if not body:
            logger.warning("Skipping %s: no body generated.", to_email)
            rp = Path(resume_path)
            log_email_send(
                TABLE_SEND_EMAILS,
                recipient_email=to_email,
                success=False,
                dry_run=args.dry_run,
                company=company or None,
                role=role or None,
                region=region,
                subject=get_subject(company, role),
                pdf_path=str(rp.resolve()),
                pdf_filename=rp.name,
                excel_path=args.excel_path,
                failure_reason="no_body",
            )
            continue

        # Clean any model-added sign-off/contact details (order matters):
        # 1) Strip obvious sign-off lines at the end
        # 2) Strip trailing contact blocks (name/email/phone/portfolio)
        # 3) Strip sign-off again (in case contact stripping exposed it)
        body = strip_leading_subject_line(
            strip_trailing_sign_off(strip_trailing_contact_block(strip_trailing_sign_off(body)))
        )
        # Append fixed signature block at the bottom (region-based phone); only one sign-off.
        body = body + "\n\n" + get_signature_block(region)

        ok, err = build_and_send(to_email, company, role, body, resume_path, config, args.dry_run, logger)
        rp = Path(resume_path)
        log_email_send(
            TABLE_SEND_EMAILS,
            recipient_email=to_email,
            success=ok,
            dry_run=args.dry_run,
            company=company or None,
            role=role or None,
            region=region,
            subject=get_subject(company, role),
            pdf_path=str(rp.resolve()),
            pdf_filename=rp.name,
            excel_path=args.excel_path,
            failure_reason=err,
        )
        if not ok:
            continue

        if i < total - 1:
            logger.info("Waiting %d seconds before next email...", DELAY_SECONDS)
            time.sleep(DELAY_SECONDS)

    logger.info("Done. Processed %d rows.", total)


if __name__ == "__main__":
    main()
