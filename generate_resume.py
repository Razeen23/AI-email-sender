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
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd
import requests

from cold_email import ensure_role_column, is_cold_email
from email_sends_db import TABLE_GENERATE_RESUME
from resume_selection import region_resume_dir
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

# Section order for a generated resume. Header, education, and the closing sections are added in code.
RESUME_SECTIONS = [
    "PROFESSIONAL SUMMARY",
    "SKILLS",
    "WORK EXPERIENCE",
    "PROJECTS",
    "EDUCATION",
    "CERTIFICATIONS",
    "AWARDS",
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
    """Same header mapping as send_emails2.normalize_columns."""
    from send_emails2 import normalize_columns as map_columns

    return map_columns(df)


def load_excel(excel_path: str, logger: logging.Logger) -> pd.DataFrame:
    if not os.path.isfile(excel_path):
        sys.exit(f"Excel file not found: {excel_path}")
    df = pd.read_excel(excel_path, engine="openpyxl")
    df = ensure_role_column(normalize_columns(df))
    required = {"Company", "Email"}
    missing = required - set(df.columns)
    if missing:
        sys.exit(f"Excel missing columns (after mapping): {missing}. Need company name and HR email. Role is optional.")
    return df


def load_profile(profile_file: str) -> str | None:
    path = Path(profile_file)
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8").strip()
    lines = [l for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]
    return "\n".join(lines).strip() or None


RESUME_FORMAT_SPEC = """
Write the resume in Markdown. Start at ## Professional Summary. Do not output the name, headline, or contact line.

Section order:
## Professional Summary
## Skills
## Work Experience
## Projects

Do not output Education, Certifications, Awards, or Languages. Those are copied from the profile after you finish.

Summary:
- Two or three short sentences in the same voice as SUMMARY TO ADAPT.
- Mention the target role once.
- Do not turn it into a keyword list.

Skills:
- Use only the saved groups and tools. Do not add a tool from the job description.
- Put the group that best matches the job first.
- One line per group, in this form: **Group:** tool, tool, tool

Work experience:
- Keep every saved job.
- Copy the title, company, and dates exactly, in this form:
  ### Title, Company | Dates
- If a location is listed on that job, put it on the next line.
- Use the saved bullets only. You may reorder them and lightly rephrase.
- Do not add a bullet, a tool, or a number that is not already in that job's bullets.
- A job with two saved bullets stays at two bullets. Do not stretch it.
- A longer job stays at five bullets or fewer. Put the most relevant bullets first.
- One idea per bullet. Vary how the lines open. Keep the plain voice of the saved bullets.
- Do not write "responsible for", "worked on", "leveraged", "spearheaded", or "passionate".

Projects:
- Choose four or five saved projects that fit this role. Put the strongest fit first.
- Do not invent a project and do not rename one.
- Use this form:
  ### Project Name
  *Tech line copied exactly*
  - three or four bullets
- Do not repeat a sentence already used under Work Experience.

Stay close to the saved length. Do not pad. Output only the Markdown resume.
"""


def build_resume_prompt(profile_text: str, role: str, company: str, jd_text: str) -> str:
    return f"""You are editing a resume a person already wrote. Select, reorder, and lightly rephrase only. Do not invent experience, skills, projects, education, dates, or numbers.

Target role: {role}
Company: {company}

Job description:
{jd_text}

{RESUME_FORMAT_SPEC}

Saved profile:
{profile_text}
"""


def choose_headline(profile: dict, role: str) -> str:
    """Keep the saved headline unless the target role is a narrower title already supported by the skills."""
    identity = profile.get("identity") or {}
    saved = (identity.get("headline") or "").strip() or "AI Full Stack Developer"
    blob = " ".join(
        f"{group.get('group', '')} {group.get('items', '')}" for group in (profile.get("skills") or [])
    ).lower()
    blob = f"{blob} {saved.lower()}"
    role_text = re.sub(
        r"\b(senior|sr\.?|lead|staff|principal|manager|director|head|intern)\b",
        " ",
        (role or "").lower(),
    )
    role_text = re.sub(r"[^a-z0-9+\s]", " ", role_text)
    role_text = re.sub(r"\s+", " ", role_text)
    checks = (
        (("react",), "React Developer", ("react",)),
        (("front end", "frontend", "front-end", "ui developer"), "Frontend Developer", ("react", "javascript")),
        (("back end", "backend", "back-end"), "Backend Developer", ("node", "php", "fastapi", "express", "python")),
        (("devops", "sre", "site reliability"), "DevOps Engineer", ("docker", "kubernetes", "github actions")),
        (("platform", "kubernetes", "k8s"), "Platform Engineer", ("kubernetes", "docker")),
        (("integration",), "Integration Engineer", ("api", "rest")),
        (("generative", "gen ai", "genai", "llm"), "AI Full Stack Developer", ("rag", "langchain", "fastapi", "ollama")),
        (("full stack", "fullstack", "full-stack"), saved, ("react",)),
    )
    for needles, headline, required in checks:
        if any(needle in role_text for needle in needles) and any(token in blob for token in required):
            return headline
    return saved


def assemble_resume_markdown(model_md: str, profile: dict, region: str) -> str:
    """Rebuild the resume so names, dates, skills, and closing sections stay on the saved facts."""
    sections = _split_markdown_sections(_strip_fences(model_md or ""))
    region_name = "UAE" if str(region).upper() == "UAE" else "INR"
    summary = _format_summary(sections.get("summary", ""), _saved_summary(profile, region_name))
    skills = _format_skills(sections.get("skills", ""), profile)
    experience = _format_experience(profile, sections.get("experience", ""), region_name)
    projects = _format_projects(profile, sections.get("projects", ""), _extract_bullets(experience))
    parts = [
        "## Professional Summary",
        "",
        summary,
        "",
        "## Skills",
        "",
        skills,
        "",
        "## Work Experience",
        "",
        experience,
        "",
        "## Projects",
        "",
        projects,
        "",
        _format_fixed_sections(profile),
    ]
    return "\n".join(part for part in parts if part is not None).strip() + "\n"


def _saved_summary(profile: dict, region: str) -> str:
    summaries = profile.get("summaries") or {}
    key = "uae" if region == "UAE" else "inr"
    text = (summaries.get(key) or "").strip()
    if text:
        return text
    other = "inr" if key == "uae" else "uae"
    return (summaries.get(other) or "").strip()


def _strip_fences(md: str) -> str:
    text = md.strip()
    text = re.sub(r"^```(?:markdown|md)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _split_markdown_sections(md: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = "preamble"
    for line in md.splitlines():
        match = re.match(r"^##\s+(.+?)\s*$", line.strip())
        if match:
            current = _section_name(match.group(1))
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return {key: "\n".join(lines).strip() for key, lines in sections.items()}


def _section_name(heading: str) -> str:
    cleaned = re.sub(r"[^a-z\s]", "", heading.lower()).strip()
    if "summary" in cleaned:
        return "summary"
    if "skill" in cleaned:
        return "skills"
    if "experience" in cleaned or cleaned == "work":
        return "experience"
    if "project" in cleaned:
        return "projects"
    if "education" in cleaned:
        return "education"
    if "certification" in cleaned:
        return "certifications"
    if "award" in cleaned:
        return "awards"
    if "language" in cleaned:
        return "languages"
    return cleaned or "other"


def _format_summary(model_section: str, saved: str) -> str:
    sentences: list[str] = []
    for line in (model_section or "").splitlines():
        text = re.sub(r"[*_`]", "", line.strip())
        if not text or text.startswith("#") or text[:1] in "-*•":
            continue
        sentences.extend(part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip())
    summary = " ".join(sentences[:3]).strip()
    banned = ("passionate", "leveraged", "spearheaded", "responsible for", "results-driven", "dynamic professional")
    if not summary or len(summary) > 700 or any(word in summary.lower() for word in banned):
        return saved
    return summary


def _format_skills(model_section: str, profile: dict) -> str:
    groups = profile.get("skills") or []
    ordered: list[str] = []
    seen: set[int] = set()
    for line in (model_section or "").splitlines():
        parsed = _skill_line(line)
        if not parsed:
            continue
        label, items = parsed
        index = _match_group(label, groups, seen)
        if index is None:
            continue
        kept = _filter_skill_items(items, groups[index].get("items") or "")
        if not kept:
            continue
        seen.add(index)
        ordered.append(f"**{groups[index].get('group', label)}:** {', '.join(kept)}")
    if not ordered:
        ordered = [
            f"**{group.get('group', '')}:** {group.get('items', '')}"
            for group in groups
            if (group.get("items") or "").strip()
        ]
        return "\n\n".join(ordered)
    for index, group in enumerate(groups):
        if index in seen or not (group.get("items") or "").strip():
            continue
        ordered.append(f"**{group.get('group', '')}:** {group.get('items', '')}")
    return "\n\n".join(ordered)


def _skill_line(line: str) -> tuple[str, str] | None:
    text = line.strip()
    if not text or text.startswith("#"):
        return None
    match = re.match(r"^\**\s*(.+?)\s*\**\s*:\s*(.+)$", text)
    if not match:
        return None
    return match.group(1).strip("* ").strip(), match.group(2).strip()


def _match_group(label: str, groups: list[dict], seen: set[int]) -> int | None:
    wanted = _norm_name(label)
    for index, group in enumerate(groups):
        if index in seen:
            continue
        name = _norm_name(group.get("group") or "")
        if name and (name == wanted or name in wanted or wanted in name):
            return index
    return None


def _filter_skill_items(model_items: str, original_items: str) -> list[str]:
    originals = [part.strip() for part in original_items.split(",") if part.strip()]
    kept: list[str] = []
    used: set[int] = set()
    for piece in model_items.split(","):
        match = _match_skill_item(piece.strip(), originals, used)
        if match is None:
            continue
        used.add(match)
        kept.append(originals[match])
    return kept


def _match_skill_item(piece: str, originals: list[str], used: set[int]) -> int | None:
    if not piece:
        return None
    piece_l = piece.lower()
    for index, original in enumerate(originals):
        if index not in used and original.lower() == piece_l:
            return index
    for index, original in enumerate(originals):
        if index in used:
            continue
        original_l = original.lower()
        if piece_l in original_l:
            return index
        if len(original_l) >= 4 and original_l in piece_l and len(piece_l) <= len(original_l) + 8:
            return index
    return None


def _format_experience(profile: dict, model_section: str, region: str) -> str:
    blocks = _split_h3(model_section)
    chunks: list[str] = []
    for entry in profile.get("experience") or []:
        saved = entry.get("bullets") or []
        cap = len(saved) if len(saved) <= 2 else min(5, len(saved))
        matched = ""
        company = (entry.get("company") or "").strip().lower()
        for title, body in blocks:
            if company and company in title.lower():
                matched = body
                break
        bullets = _keep_factual_bullets(_extract_bullets(matched), saved, cap)
        lines = [f"### {entry.get('title', '').strip()}, {entry.get('company', '').strip()} | {entry.get('dates', '').strip()}"]
        if region == "INR" and (entry.get("location") or "").strip():
            lines.extend(["", entry["location"].strip()])
        lines.append("")
        lines.extend(f"- {bullet}" for bullet in bullets)
        chunks.append("\n".join(lines))
    return "\n\n".join(chunks)


def _format_projects(profile: dict, model_section: str, experience_bullets: list[str]) -> str:
    projects = profile.get("projects") or []
    by_name = {_norm_name(project.get("name") or ""): project for project in projects if project.get("name")}
    chosen: list[tuple[dict, str]] = []
    used: set[str] = set()
    for title, body in _split_h3(model_section):
        key = _match_project(title, by_name)
        if not key or key in used:
            continue
        used.add(key)
        chosen.append((by_name[key], body))
        if len(chosen) >= 5:
            break
    if not chosen:
        chosen = [(project, "") for project in projects[:4]]
    chunks: list[str] = []
    for project, body in chosen:
        saved = project.get("bullets") or []
        cap = min(4, len(saved))
        bullets = _keep_factual_bullets(_extract_bullets(body), saved, cap)
        bullets = [bullet for bullet in bullets if not _too_similar(bullet, experience_bullets)]
        if not bullets:
            bullets = [bullet for bullet in saved if not _too_similar(bullet, experience_bullets)][:cap]
        if not bullets:
            continue
        lines = [f"### {project.get('name', '').strip()}"]
        tech = (project.get("tech") or "").strip()
        if tech:
            lines.append(f"*{tech}*")
        lines.append("")
        lines.extend(f"- {bullet}" for bullet in bullets[:cap or len(bullets)])
        chunks.append("\n".join(lines))
    return "\n\n".join(chunks)


def _format_fixed_sections(profile: dict) -> str:
    chunks: list[str] = ["## Education", ""]
    for entry in profile.get("education") or []:
        dates = f" | {entry['dates'].strip()}" if (entry.get("dates") or "").strip() else ""
        chunks.append(f"### {entry.get('degree', '').strip()}{dates}")
        if (entry.get("school") or "").strip():
            chunks.extend(["", entry["school"].strip()])
        chunks.append("")
    if profile.get("certifications"):
        chunks.extend(["## Certifications", ""])
        chunks.extend(f"- {item}" for item in profile["certifications"])
        chunks.append("")
    if profile.get("awards"):
        chunks.extend(["## Awards", ""])
        chunks.extend(f"- {item}" for item in profile["awards"])
        chunks.append("")
    languages = (profile.get("identity") or {}).get("languages") or []
    if languages:
        chunks.extend(["## Languages", "", ", ".join(languages)])
    return "\n".join(chunks).strip()


def _split_h3(text: str) -> list[tuple[str, str]]:
    parts = re.split(r"(?m)^###\s+", text or "")
    blocks: list[tuple[str, str]] = []
    for part in parts:
        if not part.strip():
            continue
        lines = part.splitlines()
        blocks.append((lines[0].strip(), "\n".join(lines[1:])))
    return blocks


def _extract_bullets(text: str) -> list[str]:
    bullets: list[str] = []
    for line in (text or "").splitlines():
        match = re.match(r"^(?:[-*•]|\d+\.)\s+(.*)$", line.strip())
        if match and match.group(1).strip():
            bullets.append(match.group(1).strip())
    return bullets


def _keep_factual_bullets(model_bullets: list[str], saved: list[str], cap: int) -> list[str]:
    if cap <= 0:
        return []
    allowed = set(re.findall(r"\d[\d,]*", " ".join(saved)))
    kept: list[str] = []
    used: set[int] = set()
    for bullet in model_bullets:
        match = _closest_saved(bullet, saved, used)
        if match is None:
            continue
        numbers = set(re.findall(r"\d[\d,]*", bullet))
        text = saved[match] if numbers - allowed else bullet.strip()
        used.add(match)
        kept.append(text)
        if len(kept) >= cap:
            break
    if kept:
        return kept
    return saved[:cap]


def _closest_saved(bullet: str, saved: list[str], used: set[int]) -> int | None:
    left = _norm_name(bullet)
    best_index = None
    best_score = 0.55
    for index, original in enumerate(saved):
        if index in used:
            continue
        right = _norm_name(original)
        if not left or not right:
            continue
        score = SequenceMatcher(None, left, right).ratio()
        if left in right or right in left:
            score = max(score, 0.9)
        if score > best_score:
            best_index = index
            best_score = score
    return best_index


def _match_project(title: str, projects: dict[str, dict]) -> str | None:
    wanted = _norm_name(title)
    if wanted in projects:
        return wanted
    for key in projects:
        if key and (key in wanted or wanted in key):
            return key
    return None


def _norm_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _too_similar(bullet: str, others: list[str]) -> bool:
    left = _norm_name(bullet)
    if not left:
        return False
    for other in others:
        right = _norm_name(other)
        if not right:
            continue
        if left in right or right in left:
            return True
        if SequenceMatcher(None, left, right).ratio() >= 0.82:
            return True
    return False


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
    """Fallback header when only a text profile is available."""
    name = _extract_name_from_profile(profile_text) or "CANDIDATE"
    headline = role.strip() if role else ""
    contact = extract_contact_from_profile(profile_text)
    contact_html = _build_contact_line_html(contact)
    import html as html_mod
    return f'<div class="resume-header"><h1>{html_mod.escape(name)}</h1><p class="resume-role">{html_mod.escape(headline)}</p><p class="resume-contact">{contact_html}</p></div>'


def build_region_header(profile: dict, role: str, region: str) -> str:
    """Name, saved headline, and the contact line for India or UAE."""
    import html as html_mod

    identity = profile.get("identity") or {}
    name = html_mod.escape((identity.get("name") or "Candidate").upper())
    headline = html_mod.escape(choose_headline(profile, role))
    contact = _region_contact_html(identity, region)
    links = _region_links_html(identity.get("links") or {})
    return (
        '<div class="resume-header">'
        f"<h1>{name}</h1>"
        f'<p class="resume-role">{headline}</p>'
        f'<p class="resume-contact">{contact}</p>'
        f'<p class="resume-links">{links}</p>'
        "</div>"
    )


def _tel_link(number: str) -> str:
    import html as html_mod

    tel = re.sub(r"[^\d+]", "", number)
    return f'<a href="tel:{html_mod.escape(tel)}">{html_mod.escape(number)}</a>'


def _region_contact_html(identity: dict, region: str) -> str:
    import html as html_mod

    phones = identity.get("phones") or {}
    location = identity.get("location") or {}
    parts: list[str] = []
    email = (identity.get("email") or "").strip()
    if email:
        parts.append(f'<a href="mailto:{html_mod.escape(email)}">{html_mod.escape(email)}</a>')
    india = (phones.get("india") or "").strip()
    uae = (phones.get("uae") or "").strip()
    if str(region).upper() == "UAE":
        if india:
            parts.append(f"INR: {_tel_link(india)}")
        if uae:
            parts.append(f"UAE: {_tel_link(uae)}")
    else:
        if india:
            parts.append(_tel_link(india))
        elif uae:
            parts.append(_tel_link(uae))
        city = (location.get("inr") or "").strip()
        if city:
            parts.append(html_mod.escape(city))
    return " | ".join(parts)


def _region_links_html(links: dict) -> str:
    import html as html_mod

    parts: list[str] = []
    for key in ("linkedin", "github", "portfolio"):
        url = (links.get(key) or "").strip()
        if not url:
            continue
        label = re.sub(r"^https?://", "", url).strip("/")
        parts.append(f'<a href="{html_mod.escape(url)}">{html_mod.escape(label)}</a>')
    return " | ".join(parts)


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


def markdown_to_html(
    md: str,
    profile_text: str | None = None,
    role: str | None = None,
    profile: dict | None = None,
    region: str | None = None,
) -> str:
    try:
        import markdown

        header_html = ""
        body_md = md
        if profile and role:
            header_html = build_region_header(profile, role, region or "INR")
            body_md = _strip_header_from_md(md)
        elif profile_text and role:
            header_html = _build_header_html(profile_text, role)
            body_md = _strip_header_from_md(md)
        body = header_html + markdown.markdown(body_md, extensions=["extra", "nl2br"])
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
    size: A4;
    margin: 14mm 13mm;
}}

body {{
    font-family: Arial, Helvetica, sans-serif;
    line-height: 1.35;
    color: #1a1a1a;
    font-size: 10.5pt;
}}

.resume-header {{
    display: block;
    margin-bottom: 8px;
    padding-bottom: 8px;
    border-bottom: 1.5px solid #1a1a1a;
}}

.resume-header h1 {{
    font-size: 18pt;
    margin: 0;
    letter-spacing: 0.6px;
    font-weight: 700;
}}

.resume-role {{
    font-size: 11pt;
    margin: 2px 0 4px 0;
    color: #222;
}}

.resume-contact,
.resume-links {{
    font-size: 9.5pt;
    margin: 0;
    line-height: 1.4;
}}

.resume-contact a,
.resume-links a {{
    color: #0a66c2;
    text-decoration: none;
}}

h2 {{
    font-size: 11pt;
    margin-top: 11px;
    margin-bottom: 4px;
    border-bottom: 1px solid #222;
    padding-bottom: 2px;
    font-weight: 700;
}}

h3 {{
    font-size: 10.5pt;
    font-weight: 700;
    margin-top: 8px;
    margin-bottom: 1px;
    color: #1a1a1a;
}}

p {{
    margin: 2px 0 4px 0;
}}

em {{
    font-style: italic;
    color: #333;
    font-size: 9.5pt;
}}

ul {{
    margin: 2px 0 6px 0;
    padding-left: 16px;
}}

li {{
    margin-bottom: 2px;
}}

strong {{
    font-weight: 700;
}}

a {{
    color: #0a66c2;
    text-decoration: none;
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
    path = region_resume_dir(base, reg) / "generated" / f"{company_slug}-{role_slug}.pdf"
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

    from backend.services.profile_service import load_profile_document, profile_has_content, render_resume_source

    profile = load_profile_document()
    if profile_has_content(profile):
        profile_text = render_resume_source(profile, region)
    else:
        profile = None
        profile_text = load_profile(config["profile_file"])
    if not profile_text:
        logger.error("Profile is empty. Add your details on the Profile page or in profile.txt.")
        sys.exit(1)

    df = load_excel(args.excel_path, logger)
    rows = list(df.to_dict("records"))
    total = len(rows)
    logger.info("Loaded %d rows from %s (region=%s).", total, args.excel_path, region)

    out_dir = region_resume_dir(config["resumes_base"], region) / "generated"
    out_dir.mkdir(parents=True, exist_ok=True)

    generated = 0
    skipped_exists = 0
    failed = 0
    sent = 0
    skipped_no_email = 0
    skipped_cold = 0
    ollama_state: dict = {}

    for i, row in enumerate(rows):
        company = str(row.get("Company", "")).strip()
        role = str(row.get("Role", "")).strip()
        if is_cold_email(role):
            logger.info(
                "[%d/%d] %s has no role. Cold mail uses the AI Full Stack resume from Send, so no tailored resume is generated.",
                i + 1,
                total,
                company or "This row",
            )
            skipped_cold += 1
            continue
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

        if profile:
            md = assemble_resume_markdown(md, profile, region)
        else:
            md = ensure_contact_links(md, profile_text)

        md_path = out_dir / f"{base_name}.md"
        md_path.write_text(md, encoding="utf-8")
        if html_to_pdf(markdown_to_html(md, profile_text, role, profile=profile, region=region), pdf_path):
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
            if send_email_for_row(
                row,
                str(pdf_path),
                logger,
                dry_run=args.dry_run,
                region=region,
                excel_path=args.excel_path,
                log_table=TABLE_GENERATE_RESUME,
                ollama_state=ollama_state,
            ):
                sent += 1
            if i < total - 1 and not args.dry_run:
                logger.info("Waiting 10 seconds before next email...")
                time.sleep(10)

    logger.info(
        "Done. Generated: %d, sent: %d, skipped (exists): %d, skipped (cold, no role): %d, skipped (no email): %d, failed: %d.",
        generated, sent, skipped_exists, skipped_cold, skipped_no_email, failed,
    )


if __name__ == "__main__":
    main()
