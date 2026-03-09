#!/usr/bin/env python3
"""
AI Email Sender: Read Excel (INR/UAE), pick resume by role, generate body via Ollama, send via SMTP.
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

# Role (normalized) -> folder name (suffix without region)
ROLE_TO_FOLDER = [
    (re.compile(r"frontend|front\s*end", re.I), "front-end"),
    (re.compile(r"full\s*stack|fullstack", re.I), "full-stack"),
    (re.compile(r"react\s*js|react", re.I), "react-js"),
    (re.compile(r"gen\s*ai|generative\s*ai|\bai\b", re.I), "gen-ai"),  # UAE only
]
DEFAULT_FOLDER = "full-stack"


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
    if region_arg:
        r = region_arg.strip().upper()
        if r in ("INR", "UAE"):
            return r
        sys.exit(f"Invalid --region: use 'inr' or 'uae'")
    path_lower = excel_path.lower()
    if "inr" in path_lower:
        return "INR"
    if "uae" in path_lower:
        return "UAE"
    sys.exit("Could not infer region from Excel path. Use --region inr or --region uae.")


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


def role_to_folder(role: str, region: str) -> str:
    r = (role or "").strip().lower()
    for pattern, folder in ROLE_TO_FOLDER:
        if pattern.search(r):
            if folder == "gen-ai" and region != "UAE":
                continue
            return f"{folder}-{region.lower()}"
    return f"{DEFAULT_FOLDER}-{region.lower()}"


def get_resume_path(resumes_base: str, region: str, role: str, logger: logging.Logger) -> str | None:
    folder_name = role_to_folder(role, region)
    dir_path = Path(resumes_base) / region / folder_name
    if not dir_path.is_dir():
        logger.error("Resume directory not found: %s", dir_path)
        return None
    pdfs = sorted(
        [f for f in dir_path.iterdir() if f.suffix.lower() == ".pdf" and ".." not in f.name],
        key=lambda p: p.name,
    )
    if not pdfs:
        logger.error("No PDF found in %s", dir_path)
        return None
    return str(pdfs[0])


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


def parse_signature_from_profile(profile_text: str | None) -> dict:
    """Extract name, email, phone, portfolio from profile text for the email signature block."""
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
            # e.g. "Phone (UAE): +971 ..." or "Phone: ..."
            sig["phone"] = line.split(":", 1)[1].strip()
        elif "portfolio" in lower or "portfilio" in lower:
            if ":" in line:
                sig["portfolio"] = line.split(":", 1)[1].strip()
    return sig


def format_signature(sig: dict) -> str:
    """Format signature block: name, then email, phone, portfolio (each on its own line)."""
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

    # Opening and company/role mention
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


def build_and_send(
    to_email: str,
    company: str,
    role: str,
    body: str,
    resume_path: str,
    config: dict,
    dry_run: bool,
    logger: logging.Logger,
) -> bool:
    msg = EmailMessage()
    # Subject: cold email (no role) and/or anonymous company (no name)
    has_role = (role or "").strip()
    has_company = (company or "").strip()
    if not has_role and not has_company:
        subject = "Reaching out"
    elif not has_role:
        subject = f"Reaching out – {company}"
    elif not has_company:
        subject = f"Application for {role}"
    else:
        subject = f"Application for {role} at {company}"
    msg["Subject"] = subject
    msg["From"] = config["from_email"]
    msg["To"] = to_email
    msg.set_content(body)
    with open(resume_path, "rb") as f:
        msg.add_attachment(f.read(), maintype="application", subtype="pdf", filename=Path(resume_path).name)
    if dry_run:
        logger.info("[DRY-RUN] Would send to %s (Company: %s, Role: %s)", to_email, company, role)
        return True
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
        return True
    except smtplib.SMTPException as e:
        logger.exception("SMTP failed for %s: %s", to_email, e)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Send personalized job emails from Excel using Ollama and SMTP.")
    parser.add_argument("excel_path", help="Path to Excel file (e.g. inr_companies_test.xlsx or uae_companies_test.xlsx)")
    parser.add_argument("--region", choices=["inr", "uae"], help="Force region (default: inferred from filename)")
    parser.add_argument("--dry-run", action="store_true", help="Generate and log only; do not send email")
    args = parser.parse_args()

    config = get_config()
    region = infer_region(args.excel_path, args.region)
    logger = setup_logging(args.dry_run)

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

    for i, row in enumerate(rows):
        company = str(row.get("Company", "")).strip()
        role = str(row.get("Role", "")).strip()
        to_email = str(row.get("Email", "")).strip()
        name = row.get("Name")
        if name is not None:
            name = str(name).strip()
        else:
            name = ""
        job_description = row.get("Job Description")
        job_description = (job_description if job_description is not None else "").strip() or None

        resume_path = get_resume_path(config["resumes_base"], region, role, logger)
        if not resume_path:
            continue

        body = generate_body(company, role, name, job_description, profile_text, config, logger)
        if not body:
            logger.warning("Skipping %s: no body generated.", to_email)
            continue

        # Append signature (name, email, phone, portfolio) at the bottom
        if profile_text:
            sig = parse_signature_from_profile(profile_text)
            signature_block = format_signature(sig)
            if signature_block:
                body = body + "\n\n" + signature_block

        success = build_and_send(to_email, company, role, body, resume_path, config, args.dry_run, logger)
        if not success:
            continue

        if i < total - 1:
            logger.info("Waiting %d seconds before next email...", DELAY_SECONDS)
            time.sleep(DELAY_SECONDS)

    logger.info("Done. Processed %d rows.", total)


if __name__ == "__main__":
    main()
