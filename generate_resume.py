#!/usr/bin/env python3
"""
Generate tailored resume PDFs using Ollama from an Excel file (same format as send_emails.py).
After each new PDF, sends one email with that PDF attached via send_generated_resume_email.py (no send_emails.py).
Reads company, role, HR email, job description per row; skips rows without JD or when PDF already exists.
Usage: python generate_resume.py inr_companies_test.xlsx [--region inr|uae] [--dry-run]
"""

import argparse
import logging
import os
import re
import sys
import time
from pathlib import Path

import pandas as pd
import requests

from send_generated_resume_email import send_email_for_row


# --- .env loading (same style as send_emails.py) ---
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


OPTIONAL_ENV = {
    "RESUMES_BASE": "resumes",
    "PROFILE_FILE": "profile.txt",
    "OLLAMA_BASE_URL": "http://localhost:11434",
    "OLLAMA_MODEL": "llama3.2",
}

# Exact section order for prompt (must match format spec below)
RESUME_SECTIONS = [
    "NAME, ROLE",
    "Contact line (Email | Phone | LinkedIn | Portfolio | GitHub)",
    "PROFESSIONAL SUMMARY",
    "WORK EXPERIENCE",
    "EDUCATION",
    "CERTIFICATIONS",
    "AWARDS & ACHIEVEMENTS",
    "SKILLS",
    "PROJECTS",
    "LANGUAGES",
]


def get_config() -> dict:
    load_dotenv()
    return {
        "resumes_base": os.environ.get("RESUMES_BASE", OPTIONAL_ENV["RESUMES_BASE"]),
        "profile_file": os.environ.get("PROFILE_FILE", OPTIONAL_ENV["PROFILE_FILE"]),
        "ollama_base_url": os.environ.get("OLLAMA_BASE_URL", OPTIONAL_ENV["OLLAMA_BASE_URL"]).rstrip("/"),
        "ollama_model": os.environ.get("OLLAMA_MODEL", OPTIONAL_ENV["OLLAMA_MODEL"]),
    }


def slugify(text: str) -> str:
    """Lowercase, replace spaces with hyphens, keep only alphanumeric and hyphens."""
    if not (text or "").strip():
        return "unknown"
    s = re.sub(r"[^\w\s-]", "", (text or "").strip().lower())
    s = re.sub(r"[-\s]+", "-", s).strip("-")
    return s or "unknown"


def normalize_region(region: str) -> str:
    """Return INR or UAE. Exits on invalid input (for CLI)."""
    r = (region or "").strip().upper()
    if r in ("INR", "UAE"):
        return r
    sys.exit(f"Invalid region: use 'inr' or 'uae', got: {region!r}")


def infer_region(excel_path: str, region_arg: str | None) -> str:
    if region_arg:
        return normalize_region(region_arg)
    path_lower = (excel_path or "").lower()
    if "inr" in path_lower:
        return "INR"
    if "uae" in path_lower:
        return "UAE"
    sys.exit("Could not infer region from Excel path. Use --region inr or --region uae.")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Same column mapping as send_emails.py."""
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
        sys.exit(f"Excel missing columns (after mapping): {missing}. Need company name, role, and HR email.")
    return df


def load_profile(profile_file: str) -> str | None:
    path = Path(profile_file)
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8").strip()
    lines = [l for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]
    return "\n".join(lines).strip() or None


RESUME_FORMAT_SPEC = """
OUTPUT FORMAT (STRICT — follow this EXACT order). Use heading hierarchy for ATS and scannability:
• ## for main section titles (WORK EXPERIENCE, EDUCATION, PROJECTS, SKILLS, etc.)
• ### for sub-topics (each company name, each project name)
• #### or ##### for sub-items where needed

**NAME** (ALL CAPS)
**ROLE** (ALL CAPS) — must be the TARGET role they are applying for (e.g. Frontend Developer), NOT their current job title.

CONTACT LINE — display the actual email and phone as the visible link text (e.g. razeen.official23@gmail.com | India: +91 9345035514), NOT the words "Email" or "Phone". Keep Markdown links so they stay clickable: [actual@email.com](mailto:...) | [India: +91 9345035514](tel:...) | [LinkedIn](url) | [Portfolio](url) | [GitHub](url). Omit any not in profile.

---

## PROFESSIONAL SUMMARY
(Short paragraph — max 4 lines. Use keywords from JD and profile for ATS.)

---

## WORK EXPERIENCE

### Company Name – Role | Date | Location

WORK EXPERIENCE RULES (STRICT):
• Each role MUST contain 5–7 bullet points
• Each bullet must describe ONE clear achievement
• Include tools + action + impact
• Prefer measurable results where possible
• Avoid vague bullets like "worked on" or "responsible for"

Bullet formula: Action verb + Tech used + What built + Impact

Example: Built RESTful APIs using Node.js + Express that automated provisioning workflows, reducing deployment time from 40 minutes to 5 minutes.

Prioritize production engineering work over basic development tasks (e.g. automation reduction, CI/CD, Slack integrations, production infra).

---

## EDUCATION

### Degree – College | Year

---

## CERTIFICATIONS
(short list)

---

## AWARDS & ACHIEVEMENTS
(short list)

---

## SKILLS

Group exactly like:
- Frontend
- Backend
- Databases
- Integrations
- DevOps & Tools
- Performance & State

---

## PROJECTS

PROJECT RULES (MANDATORY):
• Include at least 4 projects—mandatory. Prefer 5–6 when the profile has them.
• Order projects from least relevant to most relevant for the target role/JD (so recruiters see both breadth and best fit).
• Choose from profile projects: Hostzop SaaS Ecosystem, Reseller Cloud Platform, E-Invoicing Automation, SpotCard/Spotcard, CI/CD & Deployment Automation, AI-Powered Support Automation, etc.
• Each project: use ### Project Name; add a tech stack line (e.g. "Tech: Python, FastAPI, LangChain") where relevant; then exactly 5 bullets, written briefly.
• Keep each bullet short; focus on architecture, automation, and measurable outcomes—not just feature lists.

### Project Name
(Tech: ... optional line when relevant)
• 5 bullets, brief: scope, your role, tech stack, impact

---

## LANGUAGES

MANDATORY: Always include LANGUAGES section with the candidate's languages from profile (e.g. English (Fluent), Tamil (Native), Hindi). Do not omit this section.

---

TWO-PAGE RULE: Target 900–1100 words total. Use keywords from the job description and profile for ATS compatibility. Keep structure clean and scannable. Prioritize relevant experience; shorten bullets if needed; keep strong impact bullets.
"""


def build_resume_prompt(profile_text: str, role: str, company: str, jd_text: str) -> str:
    prompt = f"""You are writing a resume in Markdown. Use ONLY the information from the candidate profile below. Do NOT invent any experience, skills, education, projects, or certifications. Adapt content to the job role and JD; do not change facts. Rewrite bullets for relevance. Output ONLY clean Markdown for the resume — no commentary, no explanations.
{RESUME_FORMAT_SPEC}

Target role: {role}
Company: {company}

Job description:
{jd_text}

Candidate profile (use ONLY this information):
{profile_text}

CRITICAL: Use only information from the profile above. Do not add any experience, skill, project, education, or certification not stated there. Include at least 4 projects (mandatory), ordered from least relevant to most relevant for the role. Prioritize production engineering work over basic development tasks. Use ## for main sections and ### for company/project names so the PDF has clear heading hierarchy (h2/h3). Always include LANGUAGES. Use keywords from the JD for ATS. Output only valid Markdown for the resume, no commentary. Use bold headings with separators exactly like a professional resume."""
    return prompt


def extract_contact_from_profile(profile_text: str) -> dict:
    """Extract email, phone, phone_display, LinkedIn, Portfolio, GitHub from profile text for clickable links."""
    contact = {"email": None, "phone": None, "phone_display": None, "linkedin": None, "portfolio": None, "github": None}
    if not (profile_text or "").strip():
        return contact
    for line in profile_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if re.match(r"^email\s*:", line, re.I):
            contact["email"] = line.split(":", 1)[1].strip()
        elif re.match(r"^phone\s*\(", line, re.I) or re.match(r"^phone\s*:", line, re.I):
            # e.g. "Phone (India): +91 9345035514" -> phone_display = "India: +91 9345035514"
            val = line.split(":", 1)[1].strip() if ":" in line else ""
            if val and re.search(r"\+?\d", val):
                if contact["phone"] is None:
                    contact["phone"] = val
                    m = re.match(r"^phone\s*\(([^)]+)\)\s*:", line, re.I)
                    contact["phone_display"] = f"{m.group(1).strip()}: {val}" if m else val
        elif re.match(r"^linkedin\s*:", line, re.I):
            contact["linkedin"] = line.split(":", 1)[1].strip()
        elif re.match(r"^portfolio\s*:", line, re.I) or re.match(r"^portfilio\s*:", line, re.I):
            contact["portfolio"] = line.split(":", 1)[1].strip()
        elif re.match(r"^github\s*:", line, re.I):
            contact["github"] = line.split(":", 1)[1].strip()
        elif "Links:" in line or "links:" in line:
            continue
        else:
            # Lines under Links: section often are "LinkedIn: url"
            for key, label in [("linkedin", "LinkedIn"), ("portfolio", "Portfolio"), ("github", "GitHub")]:
                if contact[key]:
                    continue
                if re.match(rf"^{re.escape(label)}\s*:", line, re.I):
                    contact[key] = line.split(":", 1)[1].strip()
    # Fallback: any line that looks like an email or URL
    if not contact["email"]:
        m = re.search(r"[\w.+%-]+@[\w.-]+\.\w+", profile_text)
        if m:
            contact["email"] = m.group(0)
    for key, pattern in [
        ("linkedin", r"https?://(?:www\.)?linkedin\.com/[^\s)]+"),
        ("portfolio", r"https?://[^\s)]*portfolio[^\s)]*|https?://[^\s)]+\.vercel\.app[^\s)]*"),
        ("github", r"https?://(?:www\.)?github\.com/[^\s)]+"),
    ]:
        if not contact[key] and pattern:
            m = re.search(pattern, profile_text, re.I)
            if m:
                contact[key] = m.group(0)
    if not contact["phone"]:
        m = re.search(r"\+?\d[\d\s-]{8,}", profile_text)
        if m:
            contact["phone"] = m.group(0).strip()
    return contact


def build_contact_line_with_links(contact: dict) -> str:
    """Build one Markdown line with clickable links; display actual email and phone as link text."""
    parts = []
    if contact.get("email"):
        parts.append(f"[{contact['email']}](mailto:{contact['email']})")
    if contact.get("phone"):
        tel = re.sub(r"\s+", "", contact["phone"])
        display = contact.get("phone_display") or contact["phone"]
        parts.append(f"[{display}](tel:{tel})")
    if contact.get("linkedin"):
        parts.append(f"[LinkedIn]({contact['linkedin']})")
    if contact.get("portfolio"):
        parts.append(f"[Portfolio]({contact['portfolio']})")
    if contact.get("github"):
        parts.append(f"[GitHub]({contact['github']})")
    return " | ".join(parts) if parts else ""


def ensure_contact_links(md: str, profile_text: str) -> str:
    """Replace the contact line in generated markdown with clickable Markdown links from profile."""
    if not md or not profile_text:
        return md
    contact = extract_contact_from_profile(profile_text)
    new_line = build_contact_line_with_links(contact)
    if not new_line:
        return md
    lines = md.splitlines()
    for i, line in enumerate(lines):
        if i > 15:
            break
        stripped = line.strip()
        if "|" not in stripped or stripped.startswith("|") or stripped.startswith("-"):
            continue
        if any(x in stripped.lower() for x in ("email", "phone", "linkedin", "portfolio", "github", "@", "http")):
            lines[i] = new_line
            return "\n".join(lines)
    return md


def _build_contact_line_html(contact: dict) -> str:
    """Build contact line as HTML <a> tags for the PDF header."""
    import html as html_mod
    parts = []
    if contact.get("email"):
        parts.append(f'<a href="mailto:{html_mod.escape(contact["email"])}">{html_mod.escape(contact["email"])}</a>')
    if contact.get("phone"):
        tel = re.sub(r"\s+", "", contact["phone"])
        display = html_mod.escape(contact.get("phone_display") or contact["phone"])
        parts.append(f'<a href="tel:{html_mod.escape(tel)}">{display}</a>')
    if contact.get("linkedin"):
        url = html_mod.escape(contact["linkedin"])
        parts.append(f'<a href="{url}">LinkedIn</a>')
    if contact.get("portfolio"):
        url = html_mod.escape(contact["portfolio"])
        parts.append(f'<a href="{url}">Portfolio</a>')
    if contact.get("github"):
        url = html_mod.escape(contact["github"])
        parts.append(f'<a href="{url}">GitHub</a>')
    return " | ".join(parts) if parts else ""


def _extract_name_from_profile(profile_text: str) -> str:
    """Extract candidate name (ALL CAPS for header) from profile."""
    if not (profile_text or "").strip():
        return ""
    for line in profile_text.splitlines():
        line = line.strip()
        if re.match(r"^name\s*:", line, re.I):
            name = line.split(":", 1)[1].strip()
            return name.upper() if name else ""
    return ""


# Section titles the AI may use (bold or ##); after these we keep content
_RESUME_SECTION_PATTERNS = (
    r"^---\s*$",
    r"^##\s+",
    r"^\*\*PROFESSIONAL SUMMARY\*\*",
    r"^\*\*WORK EXPERIENCE\*\*",
    r"^\*\*EDUCATION\*\*",
    r"^\*\*CERTIFICATIONS\*\*",
    r"^\*\*AWARDS",
    r"^\*\*SKILLS\*\*",
    r"^\*\*PROJECTS\*\*",
    r"^\*\*LANGUAGES\*\*",
)


def _strip_header_from_md(md: str) -> str:
    """Remove the first block (name, role, contact) from markdown so only our HTML header is used. Strips until we see --- or a section header (## or **SECTION**)."""
    if not md or not md.strip():
        return md
    lines = md.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        for pat in _RESUME_SECTION_PATTERNS:
            if re.match(pat, stripped, re.I):
                return "\n".join(lines[i:]).lstrip()
    return md


def _build_header_html(profile_text: str, role: str) -> str:
    """Build a fixed HTML header (name, role, contact + social links) so it always appears in the PDF."""
    name = _extract_name_from_profile(profile_text) or "CANDIDATE"
    role_escaped = role.upper() if role else ""
    contact = extract_contact_from_profile(profile_text)
    contact_html = _build_contact_line_html(contact)
    import html as html_mod
    return f'<div class="resume-header"><h1>{html_mod.escape(name)}</h1><p class="resume-role">{html_mod.escape(role_escaped)}</p><p class="resume-contact">{contact_html}</p></div>'


def generate_markdown(prompt: str, config: dict) -> str | None:
    url = f"{config['ollama_base_url']}/api/generate"
    payload = {"model": config["ollama_model"], "prompt": prompt, "stream": False}
    try:
        resp = requests.post(url, json=payload, timeout=180)
        resp.raise_for_status()
        data = resp.json()
        return (data.get("response") or "").strip()
    except requests.RequestException as e:
        return None


def markdown_to_html(md: str, profile_text: str | None = None, role: str | None = None) -> str:
    try:
        import markdown
        if profile_text and role:
            header_html = _build_header_html(profile_text, role)
            body_md = _strip_header_from_md(md)
            body = header_html + markdown.markdown(body_md, extensions=["extra", "nl2br"])
        else:
            body = markdown.markdown(md, extensions=["extra", "nl2br"])
    except ImportError:
        import html as html_mod
        body = f"<pre>{html_mod.escape(md)}</pre>"

    return f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>

<style>

@page {{
    margin: 28px;
}}

body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    line-height: 1.45;
    color: #111;
    font-size: 11.2pt;
}}

.resume-header {{
    display: block;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid #ddd;
}}

.resume-header h1 {{
    font-size: 22pt;
    margin: 0;
    letter-spacing: 1px;
}}

.resume-role {{
    font-size: 12pt;
    margin: 4px 0 6px 0;
    color: #333;
}}

.resume-contact {{
    font-size: 10pt;
    margin: 0;
}}

.resume-contact a {{
    color: #0a66c2;
    text-decoration: none;
}}

h1 {{
    font-size: 22pt;
    margin: 0;
    letter-spacing: 1px;
}}

h2 {{
    font-size: 12pt;
    margin-top: 18px;
    margin-bottom: 6px;
    border-bottom: 1px solid #ddd;
    padding-bottom: 4px;
    letter-spacing: .5px;
}}

h3 {{
    font-size: 11pt;
    font-weight: 600;
    margin-top: 12px;
    margin-bottom: 4px;
    color: #1a1a1a;
}}

h4 {{
    font-size: 10.5pt;
    font-weight: 600;
    margin-top: 10px;
    margin-bottom: 2px;
    color: #333;
}}

h5 {{
    font-size: 10pt;
    font-weight: 600;
    margin-top: 8px;
    margin-bottom: 2px;
    color: #444;
}}

p {{
    margin: 6px 0;
}}

ul {{
    margin: 6px 0 12px 0;
    padding-left: 18px;
}}

li {{
    margin-bottom: 6px;
    padding-left: 2px;
}}

li::marker {{
    color: #0a66c2;
    font-size: 10pt;
}}

strong {{
    font-weight: 600;
}}

a {{
    color: #0a66c2;
    text-decoration: none;
}}

a:hover {{
    text-decoration: underline;
}}

hr {{
    border: none;
    border-top: 1px solid #ddd;
    margin: 10px 0;
}}

.header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}}

.contact {{
    font-size: 10pt;
    text-align: right;
}}

.role {{
    font-size: 12pt;
    margin-top: 2px;
    color: #333;
}}

</style>
</head>

<body>

{body}

</body>
</html>
"""

def html_to_pdf(html_content: str, pdf_path: Path) -> bool:
    try:
        from weasyprint import HTML
        HTML(string=html_content).write_pdf(pdf_path)
        return True
    except ImportError:
        return False


def get_resume_path(
    role: str,
    company: str,
    region: str,
    resumes_base: str | None = None,
) -> str | None:
    """
    Return path to generated resume PDF if it exists, else None.
    Use this in send_emails.py: if get_resume_path(role, company, region) is not None, use it; else use default resume.
    """
    load_dotenv()
    base = (resumes_base or os.environ.get("RESUMES_BASE") or OPTIONAL_ENV["RESUMES_BASE"]).strip()
    reg = (region or "").strip().upper()
    if reg not in ("INR", "UAE"):
        return None
    company_slug = slugify(company)
    role_slug = slugify(role)
    path = Path(base) / reg / "generated" / f"{company_slug}-{role_slug}.pdf"
    if path.is_file():
        return str(path)
    return None


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("generate_resume")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(ch)
    return logger


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate tailored resume PDFs from an Excel file (same format as send_emails.py).",
    )
    parser.add_argument("excel_path", help="Path to Excel file (company, role, HR email, job description columns)")
    parser.add_argument("--region", default=None, help="Region: inr or uae (default: infer from filename)")
    parser.add_argument("--dry-run", action="store_true", help="Generate PDFs only; do not send emails")
    args = parser.parse_args()

    logger = setup_logging()
    config = get_config()
    region = infer_region(args.excel_path, args.region)

    profile_text = load_profile(config["profile_file"])
    if not profile_text:
        logger.error("Profile file not found or empty. Set PROFILE_FILE in .env or create profile.txt.")
        sys.exit(1)

    df = load_excel(args.excel_path, logger)
    rows = list(df.to_dict("records"))
    total = len(rows)
    logger.info("Loaded %d rows from %s (region=%s).", total, args.excel_path, region)

    out_dir = Path(config["resumes_base"]) / region / "generated"
    out_dir.mkdir(parents=True, exist_ok=True)

    generated = 0
    skipped_exists = 0
    failed = 0
    sent = 0
    skipped_no_email = 0

    for i, row in enumerate(rows):
        company = str(row.get("Company", "")).strip()
        role = str(row.get("Role", "")).strip()
        jd = row.get("Job Description")
        if pd.isna(jd):
            jd_text = None
        else:
            jd_text = str(jd).strip() or None
        if not jd_text:
            jd_text = "(No job description provided.)"

        company_slug = slugify(company)
        role_slug = slugify(role)
        base_name = f"{company_slug}-{role_slug}"
        pdf_path = out_dir / f"{base_name}.pdf"

        if pdf_path.is_file():
            skipped_exists += 1
            logger.info("[%d/%d] Skipped %s / %s (PDF already exists).", i + 1, total, company, role)
            continue

        logger.info("[%d/%d] Generating resume for %s / %s...", i + 1, total, company, role)
        prompt = build_resume_prompt(profile_text, role, company, jd_text)
        md = generate_markdown(prompt, config)

        if not md:
            failed += 1
            logger.warning("[%d/%d] Ollama failed for %s / %s.", i + 1, total, company, role)
            continue

        md = ensure_contact_links(md, profile_text)

        md_path = out_dir / f"{base_name}.md"
        md_path.write_text(md, encoding="utf-8")
        if html_to_pdf(markdown_to_html(md, profile_text, role), pdf_path):
            generated += 1
            logger.info("[%d/%d] Saved PDF: %s", i + 1, total, pdf_path)
        else:
            generated += 1
            logger.info("[%d/%d] Saved Markdown only (WeasyPrint not installed): %s", i + 1, total, md_path)

        to_email = str(row.get("Email", "")).strip()
        if not to_email or "@" not in to_email:
            skipped_no_email += 1
            logger.info("[%d/%d] Skipped sending (no valid email).", i + 1, total)
        else:
            if send_email_for_row(row, str(pdf_path), logger, dry_run=args.dry_run):
                sent += 1
            if i < total - 1 and not args.dry_run:
                logger.info("Waiting 10 seconds before next email...")
                time.sleep(10)

    logger.info(
        "Done. Generated: %d, sent: %d, skipped (exists): %d, skipped (no email): %d, failed: %d.",
        generated, sent, skipped_exists, skipped_no_email, failed,
    )


if __name__ == "__main__":
    main()
