from __future__ import annotations

import json
import re
import uuid
import zipfile
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree

from backend.models.schemas import ProfileDocument
from backend.paths import BASE_CV_INR, BASE_CV_UAE, PROFILE_JSON, PROFILE_PATH

_W_P = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"
_W_T = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"

_MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?"
_DATE_RE = re.compile(
    rf"({_MONTH}\s+\d{{4}}\s*[-–—]\s*(?:Present|Current|{_MONTH}\s+\d{{4}})|\d{{4}}\s*[-–—]\s*(?:\d{{4}}|Present|Current))",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"[\w.+%-]+@[\w.-]+\.\w+")
_PHONE_RE = re.compile(r"\+\d{1,3}(?:[\s-]?\d{2,})+")

_SECTION_KEYS = {
    "professional summary": "summary",
    "summary": "summary",
    "skills": "skills",
    "work experience": "experience",
    "experience": "experience",
    "professional experience": "experience",
    "projects": "projects",
    "education": "education",
    "certifications": "certifications",
    "awards": "awards",
    "awards & achievements": "awards",
    "awards and achievements": "awards",
    "languages": "languages",
}


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def empty_profile() -> dict:
    return ProfileDocument().model_dump()


def profile_has_content(profile: dict | None) -> bool:
    if not profile:
        return False
    identity = profile.get("identity") or {}
    return bool(
        (identity.get("name") or "").strip()
        or profile.get("experience")
        or profile.get("projects")
        or (profile.get("summaries") or {}).get("inr")
        or (profile.get("summaries") or {}).get("uae")
    )


def _clean_list(values: list[str] | None) -> list[str]:
    return [item.strip() for item in (values or []) if item and item.strip()]


def normalize_profile(data: dict) -> dict:
    dumped = ProfileDocument.model_validate(data).model_dump()
    for key in ("skills", "experience", "projects", "education"):
        for item in dumped[key]:
            if not item.get("id"):
                item["id"] = new_id()
    for entry in dumped["experience"]:
        entry["bullets"] = _clean_list(entry.get("bullets"))
    for entry in dumped["projects"]:
        entry["bullets"] = _clean_list(entry.get("bullets"))
    dumped["certifications"] = _clean_list(dumped.get("certifications"))
    dumped["awards"] = _clean_list(dumped.get("awards"))
    dumped["identity"]["languages"] = _clean_list(dumped["identity"].get("languages"))
    dumped["email_rules"] = (dumped.get("email_rules") or "").strip()
    return dumped


def load_profile_document() -> dict:
    if PROFILE_JSON.is_file():
        return normalize_profile(json.loads(PROFILE_JSON.read_text(encoding="utf-8")))
    if BASE_CV_INR.is_file() and BASE_CV_UAE.is_file():
        return import_base_cvs(save=True)
    return empty_profile()


def save_profile_document(data: dict) -> dict:
    existing_rules = ""
    if PROFILE_JSON.is_file():
        try:
            existing_rules = (json.loads(PROFILE_JSON.read_text(encoding="utf-8")).get("email_rules") or "").strip()
        except (OSError, json.JSONDecodeError):
            existing_rules = ""
    profile = normalize_profile(data)
    if not profile["email_rules"] and existing_rules:
        profile["email_rules"] = existing_rules
    PROFILE_JSON.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_JSON.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return profile


def read_email_rules() -> str:
    if not PROFILE_PATH.is_file():
        return ""
    text = PROFILE_PATH.read_text(encoding="utf-8")
    match = re.search(r"EMAIL STYLE RULES.*", text, flags=re.IGNORECASE | re.DOTALL)
    return match.group(0).strip() if match else ""


def import_base_cvs(*, save: bool) -> dict:
    if not BASE_CV_INR.is_file() or not BASE_CV_UAE.is_file():
        raise ValueError("Base CVs were not found in resumes/.")
    existing_rules = ""
    if PROFILE_JSON.is_file():
        try:
            existing_rules = (json.loads(PROFILE_JSON.read_text(encoding="utf-8")).get("email_rules") or "").strip()
        except (OSError, json.JSONDecodeError):
            existing_rules = ""
    profile = merge_base_profiles(parse_docx(BASE_CV_INR), parse_docx(BASE_CV_UAE))
    profile["email_rules"] = existing_rules or read_email_rules()
    profile = normalize_profile(profile)
    if save:
        PROFILE_JSON.parent.mkdir(parents=True, exist_ok=True)
        PROFILE_JSON.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return profile


def import_docx_file(path: Path, region: str, existing: dict | None = None) -> dict:
    parsed = parse_docx(path)
    region_key = (region or "BOTH").strip().upper()
    if region_key not in {"INR", "UAE", "BOTH"}:
        raise ValueError("Region must be INR, UAE, or BOTH.")
    profile = deepcopy(existing) if existing else empty_profile()
    _apply_shared(profile, parsed, region_key)
    return save_profile_document(profile)


def summary_for_region(profile: dict, region: str) -> str:
    key = "uae" if str(region).upper() == "UAE" else "inr"
    summaries = profile.get("summaries") or {}
    text = (summaries.get(key) or "").strip()
    if text:
        return text
    other = "inr" if key == "uae" else "uae"
    return (summaries.get(other) or "").strip()


def render_resume_source(profile: dict, region: str) -> str:
    region_name = "UAE" if str(region).upper() == "UAE" else "INR"
    identity = profile.get("identity") or {}
    lines = [
        "Use ONLY the facts below. Do not add jobs, projects, skills, dates, or numbers that are not written here.",
        f"Name: {identity.get('name', '')}",
        f"Headline: {identity.get('headline', '')}",
        f"Target region: {region_name}",
        "",
        "SUMMARY TO ADAPT:",
        summary_for_region(profile, region_name),
        "",
        "SKILLS:",
    ]
    for group in profile.get("skills") or []:
        lines.append(f"- {group.get('group', '')}: {group.get('items', '')}")
    lines.extend(["", "WORK EXPERIENCE:"])
    for entry in profile.get("experience") or []:
        location = ""
        if region_name == "INR" and (entry.get("location") or "").strip():
            location = f" | {entry['location'].strip()}"
        lines.append(f"- {entry.get('title', '')}, {entry.get('company', '')} | {entry.get('dates', '')}{location}")
        for bullet in entry.get("bullets") or []:
            lines.append(f"  • {bullet}")
        lines.append("")
    lines.append("PROJECTS:")
    for project in profile.get("projects") or []:
        lines.append(f"- {project.get('name', '')}")
        if (project.get("tech") or "").strip():
            lines.append(f"  Tech: {project['tech'].strip()}")
        for bullet in project.get("bullets") or []:
            lines.append(f"  • {bullet}")
        lines.append("")
    lines.append("EDUCATION:")
    for entry in profile.get("education") or []:
        lines.append(f"- {entry.get('degree', '')} | {entry.get('dates', '')} | {entry.get('school', '')}")
    lines.extend(["", "CERTIFICATIONS:"])
    for item in profile.get("certifications") or []:
        lines.append(f"- {item}")
    lines.extend(["", "AWARDS:"])
    for item in profile.get("awards") or []:
        lines.append(f"- {item}")
    languages = ", ".join(identity.get("languages") or [])
    lines.extend(["", "LANGUAGES:", languages])
    return "\n".join(lines).strip()


def render_email_profile(profile: dict | None = None) -> str | None:
    document = profile or load_profile_document()
    if not profile_has_content(document):
        return None
    identity = document.get("identity") or {}
    phones = identity.get("phones") or {}
    links = identity.get("links") or {}
    lines = [
        f"Name: {identity.get('name', '')}",
        f"Email: {identity.get('email', '')}",
        f"Phone (India): {phones.get('india', '')}",
        f"Phone (UAE): {phones.get('uae', '')}",
        f"Headline: {identity.get('headline', '')}",
        f"Location (India): {(identity.get('location') or {}).get('inr', '')}",
        f"LinkedIn: {links.get('linkedin', '')}",
        f"Portfolio: {links.get('portfolio', '')}",
        f"GitHub: {links.get('github', '')}",
        "",
        "PROFESSIONAL SUMMARY (INDIA)",
        (document.get("summaries") or {}).get("inr", ""),
        "",
        "PROFESSIONAL SUMMARY (UAE)",
        (document.get("summaries") or {}).get("uae", ""),
        "",
        "SKILLS",
    ]
    for group in document.get("skills") or []:
        lines.append(f"{group.get('group', '')}: {group.get('items', '')}")
    lines.extend(["", "WORK EXPERIENCE"])
    for entry in document.get("experience") or []:
        location = f" | {entry['location']}" if entry.get("location") else ""
        lines.append(f"{entry.get('title', '')} — {entry.get('company', '')} | {entry.get('dates', '')}{location}")
        for bullet in entry.get("bullets") or []:
            lines.append(f"• {bullet}")
        lines.append("")
    lines.append("PROJECTS")
    for project in document.get("projects") or []:
        lines.append(project.get("name", ""))
        if project.get("tech"):
            lines.append(f"Tech: {project['tech']}")
        for bullet in project.get("bullets") or []:
            lines.append(f"• {bullet}")
        lines.append("")
    lines.append("EDUCATION")
    for entry in document.get("education") or []:
        lines.append(f"{entry.get('degree', '')} | {entry.get('dates', '')} | {entry.get('school', '')}")
    lines.extend(["", "CERTIFICATIONS"])
    for item in document.get("certifications") or []:
        lines.append(f"• {item}")
    lines.extend(["", "AWARDS"])
    for item in document.get("awards") or []:
        lines.append(f"• {item}")
    languages = ", ".join(identity.get("languages") or [])
    lines.extend(["", "LANGUAGES", languages])
    rules = (document.get("email_rules") or "").strip()
    if rules:
        lines.extend(["", rules])
    return "\n".join(lines).strip()


def email_profile_or_none() -> str | None:
    try:
        return render_email_profile()
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def docx_paragraphs(path: Path) -> list[str]:
    if path.suffix.lower() != ".docx":
        raise ValueError("Only .docx files can be imported.")
    try:
        with zipfile.ZipFile(path) as archive:
            xml = archive.read("word/document.xml")
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        raise ValueError("Could not read that Word file.") from exc
    root = ElementTree.fromstring(xml)
    paragraphs: list[str] = []
    for node in root.iter(_W_P):
        text = "".join(item.text or "" for item in node.iter(_W_T)).strip()
        if text:
            paragraphs.append(text)
    if not paragraphs:
        raise ValueError("That Word file has no text.")
    return paragraphs


def parse_docx(path: Path) -> dict:
    return profile_from_paragraphs(docx_paragraphs(path))


def parse_resume_text(text: str) -> dict:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if not lines:
        raise ValueError("That resume has no text.")
    return profile_from_paragraphs(lines)


def profile_from_paragraphs(paragraphs: list[str]) -> dict:
    header, sections = _split_sections(paragraphs)
    if "summary" not in sections or "experience" not in sections:
        raise ValueError("The resume needs Professional Summary and Work Experience headings.")
    identity = _parse_header(header)
    identity["languages"] = _parse_languages(sections.get("languages") or [])
    return {
        "identity": identity,
        "summary": " ".join(sections.get("summary") or []).strip(),
        "skills": _parse_skills(sections.get("skills") or []),
        "experience": _parse_experience(sections.get("experience") or []),
        "projects": _parse_projects(sections.get("projects") or []),
        "education": _parse_education(sections.get("education") or []),
        "certifications": _parse_plain_list(sections.get("certifications") or []),
        "awards": _parse_plain_list(sections.get("awards") or []),
        "location": identity.pop("location_text", ""),
    }


def combine_parsed_resumes(base: dict, parsed_resumes: list[dict], region: str) -> dict:
    """Keep contact details from the saved profile and union jobs, projects, and skills from the selected resumes."""
    profile = deepcopy(base)
    profile["skills"] = []
    profile["experience"] = []
    profile["projects"] = []
    profile["education"] = []
    profile["certifications"] = []
    profile["awards"] = []
    summary_key = "uae" if str(region).upper() == "UAE" else "inr"
    profile["summaries"] = {"inr": "", "uae": ""}
    for parsed in parsed_resumes:
        _merge_resume_facts(profile, parsed, summary_key)
    if not (profile["summaries"].get(summary_key) or "").strip():
        profile["summaries"][summary_key] = ((base.get("summaries") or {}).get(summary_key) or "").strip()
    if not profile["identity"].get("languages"):
        profile["identity"]["languages"] = list((base.get("identity") or {}).get("languages") or [])
    return normalize_profile(profile)


def _merge_resume_facts(profile: dict, parsed: dict, summary_key: str) -> None:
    for group in parsed.get("skills") or []:
        name = (group.get("group") or "").strip()
        items = (group.get("items") or "").strip()
        if not name or not items:
            continue
        key = _fact_key(name)
        match = next((item for item in profile["skills"] if _fact_key(item.get("group") or "") == key), None)
        if match:
            match["items"] = _union_csv(match.get("items") or "", items)
        else:
            profile["skills"].append({"id": new_id(), "group": name, "items": items})
    for entry in parsed.get("experience") or []:
        if not (entry.get("title") or entry.get("company")):
            continue
        key = _fact_key(f"{entry.get('title', '')} {entry.get('company', '')}")
        match = next(
            (
                item
                for item in profile["experience"]
                if _fact_key(f"{item.get('title', '')} {item.get('company', '')}") == key
            ),
            None,
        )
        if match:
            match["bullets"] = _union_lines(match.get("bullets") or [], entry.get("bullets") or [])
            if not (match.get("dates") or "").strip() and (entry.get("dates") or "").strip():
                match["dates"] = entry["dates"]
            if not (match.get("location") or "").strip() and (entry.get("location") or "").strip():
                match["location"] = entry["location"]
        else:
            profile["experience"].append({**entry, "id": new_id(), "bullets": list(entry.get("bullets") or [])})
    for project in parsed.get("projects") or []:
        name = (project.get("name") or "").strip()
        if not name:
            continue
        key = _fact_key(name)
        match = next((item for item in profile["projects"] if _fact_key(item.get("name") or "") == key), None)
        if match:
            match["bullets"] = _union_lines(match.get("bullets") or [], project.get("bullets") or [])
            if len((project.get("tech") or "")) > len(match.get("tech") or ""):
                match["tech"] = project["tech"]
        else:
            profile["projects"].append({**project, "id": new_id(), "bullets": list(project.get("bullets") or [])})
    for entry in parsed.get("education") or []:
        key = _fact_key(f"{entry.get('degree', '')} {entry.get('school', '')}")
        if not key:
            continue
        if any(_fact_key(f"{item.get('degree', '')} {item.get('school', '')}") == key for item in profile["education"]):
            continue
        profile["education"].append({**entry, "id": new_id()})
    profile["certifications"] = _union_lines(profile.get("certifications") or [], parsed.get("certifications") or [])
    profile["awards"] = _union_lines(profile.get("awards") or [], parsed.get("awards") or [])
    summary = (parsed.get("summary") or "").strip()
    current = (profile["summaries"].get(summary_key) or "").strip()
    if summary and len(summary) > len(current):
        profile["summaries"][summary_key] = summary
    languages = profile["identity"].setdefault("languages", [])
    for language in (parsed.get("identity") or {}).get("languages") or []:
        if language and language not in languages:
            languages.append(language)


def _fact_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _union_lines(current: list[str], incoming: list[str]) -> list[str]:
    merged = [item.strip() for item in current if item and item.strip()]
    seen = {_fact_key(item) for item in merged}
    for item in incoming:
        text = (item or "").strip()
        key = _fact_key(text)
        if key and key not in seen:
            merged.append(text)
            seen.add(key)
    return merged


def _union_csv(current: str, incoming: str) -> str:
    return ", ".join(_union_lines(
        [part.strip() for part in (current or "").split(",") if part.strip()],
        [part.strip() for part in (incoming or "").split(",") if part.strip()],
    ))


def merge_base_profiles(inr: dict, uae: dict) -> dict:
    profile = empty_profile()
    _apply_shared(profile, inr, "INR")
    profile["summaries"]["uae"] = (uae.get("summary") or "").strip()
    phones = uae.get("identity", {}).get("phones") or {}
    if phones.get("india") and not profile["identity"]["phones"]["india"]:
        profile["identity"]["phones"]["india"] = phones["india"]
    if phones.get("uae"):
        profile["identity"]["phones"]["uae"] = phones["uae"]
    if (uae.get("location") or "").strip() and not re.search(r"india|chennai", uae["location"], re.I):
        profile["identity"]["location"]["uae"] = uae["location"].strip()
    links = uae.get("identity", {}).get("links") or {}
    for key in ("linkedin", "github", "portfolio"):
        if links.get(key) and not profile["identity"]["links"][key]:
            profile["identity"]["links"][key] = links[key]
    return profile


def _apply_shared(profile: dict, parsed: dict, region_key: str) -> None:
    identity = parsed.get("identity") or {}
    for key in ("name", "headline", "email"):
        if (identity.get(key) or "").strip():
            profile["identity"][key] = identity[key].strip()
    phones = identity.get("phones") or {}
    for key in ("india", "uae"):
        if (phones.get(key) or "").strip():
            profile["identity"]["phones"][key] = phones[key].strip()
    links = identity.get("links") or {}
    for key in ("linkedin", "github", "portfolio"):
        if (links.get(key) or "").strip():
            profile["identity"]["links"][key] = links[key].strip()
    if identity.get("languages"):
        profile["identity"]["languages"] = identity["languages"]
    location = (parsed.get("location") or "").strip()
    if region_key == "UAE":
        profile["summaries"]["uae"] = (parsed.get("summary") or "").strip()
        profile["identity"]["location"]["uae"] = location
    elif region_key == "INR":
        profile["summaries"]["inr"] = (parsed.get("summary") or "").strip()
        if location:
            profile["identity"]["location"]["inr"] = location
    else:
        summary = (parsed.get("summary") or "").strip()
        profile["summaries"]["inr"] = summary
        profile["summaries"]["uae"] = summary
        if location and re.search(r"india|chennai", location, re.I):
            profile["identity"]["location"]["inr"] = location
        elif location:
            profile["identity"]["location"]["uae"] = location
    for key in ("skills", "experience", "projects", "education", "certifications", "awards"):
        profile[key] = parsed.get(key) or []


def _split_sections(paragraphs: list[str]) -> tuple[list[str], dict[str, list[str]]]:
    header: list[str] = []
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for paragraph in paragraphs:
        plain = _plain_line(paragraph)
        if not plain:
            continue
        key = _section_key(plain)
        if key:
            current = key
            sections.setdefault(current, [])
            continue
        if current is None:
            header.append(plain)
        else:
            sections[current].append(plain)
    return header, sections


def _plain_line(line: str) -> str:
    return re.sub(r"^#+\s*", "", (line or "").strip())


def _section_key(line: str) -> str | None:
    cleaned = _plain_line(line).replace("*", "")
    cleaned = re.sub(r"[:\s]+$", "", cleaned).lower()
    return _SECTION_KEYS.get(cleaned)


def _parse_header(lines: list[str]) -> dict:
    name = lines[0].strip() if lines else ""
    headline = lines[1].strip() if len(lines) > 1 else ""
    contact_lines: list[str] = []
    link_lines: list[str] = []
    for line in lines[2:]:
        lower = line.lower()
        if any(token in lower for token in ("linkedin", "github", "vercel", "portfolio", "http")):
            link_lines.append(line)
        else:
            contact_lines.append(line)
    contact = " | ".join(contact_lines)
    email_match = _EMAIL_RE.search(contact)
    phones = {"india": "", "uae": ""}
    for match in _PHONE_RE.findall(contact):
        slot = _phone_slot(match)
        if slot and not phones[slot]:
            phones[slot] = re.sub(r"\s+", " ", match).strip()
    location_parts: list[str] = []
    for part in re.split(r"\|", contact):
        piece = part.strip()
        if not piece or _EMAIL_RE.search(piece) or _PHONE_RE.search(piece):
            continue
        piece = re.sub(r"^(?:INR|UAE|India|Phone)\s*:\s*", "", piece, flags=re.I).strip()
        if piece:
            location_parts.append(piece)
    links = {"linkedin": "", "github": "", "portfolio": ""}
    for part in re.split(r"\|", " | ".join(link_lines)):
        piece = part.strip()
        lower = piece.lower()
        if "linkedin" in lower and not links["linkedin"]:
            links["linkedin"] = _ensure_https(piece)
        elif "github" in lower and not links["github"]:
            links["github"] = _ensure_https(piece)
        elif piece and not links["portfolio"] and any(token in lower for token in ("vercel", "portfolio", "http")):
            links["portfolio"] = _ensure_https(piece)
    return {
        "name": name,
        "headline": headline,
        "email": email_match.group(0) if email_match else "",
        "phones": phones,
        "links": links,
        "languages": [],
        "location_text": ", ".join(location_parts),
    }


def _phone_slot(number: str) -> str:
    digits = re.sub(r"\D", "", number)
    if digits.startswith("971"):
        return "uae"
    if digits.startswith("91"):
        return "india"
    return ""


def _ensure_https(value: str) -> str:
    text = value.strip()
    if text.lower().startswith(("http://", "https://")):
        return text
    return "https://" + text.lstrip("/")


def split_date(line: str) -> tuple[str, str]:
    match = _DATE_RE.search(line)
    if not match:
        return line.strip(), ""
    dates = re.sub(r"\s+", " ", match.group(1)).replace("–", "-").replace("—", "-").strip()
    left = (line[: match.start()] + line[match.end() :]).strip(" ,|-")
    return left, dates


def _clean_bullet(line: str) -> str:
    return re.sub(r"^(?:[•\-\*]|\d+[.)])\s*", "", line.strip()).strip()


def _is_sentence(line: str) -> bool:
    text = line.strip()
    return text.endswith(".") or text[:1] in "•-*"


def _parse_experience(lines: list[str]) -> list[dict]:
    entries: list[dict] = []
    current: dict | None = None
    for line in lines:
        left, dates = split_date(line)
        if dates and not _is_sentence(line):
            if current:
                entries.append(current)
            title, company = _split_title_company(left)
            current = {
                "id": new_id(),
                "title": title,
                "company": company,
                "dates": dates,
                "location": "",
                "bullets": [],
            }
            continue
        if current is None:
            continue
        if not current["location"] and not _is_sentence(line) and len(line.strip()) <= 48:
            current["location"] = line.strip()
            continue
        bullet = _clean_bullet(line)
        if bullet:
            current["bullets"].append(bullet)
    if current:
        entries.append(current)
    return entries


def _split_title_company(left: str) -> tuple[str, str]:
    if "," not in left:
        return left.strip(), ""
    title, company = left.split(",", 1)
    return title.strip(), company.strip().rstrip(",")


def _is_tech_line(line: str, following: str = "") -> bool:
    text = re.sub(r"^\*+|\*+$", "", line.strip()).strip()
    if not text or text.endswith(".") or text[:1] in "•-":
        return False
    if "," in text:
        return True
    return len(text) <= 48 and _is_sentence(following)


def _parse_projects(lines: list[str]) -> list[dict]:
    projects: list[dict] = []
    index = 0
    while index < len(lines):
        name = lines[index].strip()
        index += 1
        tech = ""
        following = lines[index + 1] if index + 1 < len(lines) else ""
        if index < len(lines) and _is_tech_line(lines[index], following):
            tech = re.sub(r"^\*+|\*+$", "", lines[index].strip()).strip()
            index += 1
        bullets: list[str] = []
        while index < len(lines) and _is_sentence(lines[index]):
            bullet = _clean_bullet(lines[index])
            if bullet:
                bullets.append(bullet)
            index += 1
        if name:
            projects.append({"id": new_id(), "name": name, "tech": tech, "bullets": bullets})
    return projects


def _parse_education(lines: list[str]) -> list[dict]:
    entries: list[dict] = []
    index = 0
    while index < len(lines):
        degree, dates = split_date(lines[index])
        index += 1
        school = ""
        if index < len(lines) and not split_date(lines[index])[1]:
            school = lines[index].strip()
            index += 1
        if degree or school:
            entries.append({"id": new_id(), "degree": degree.strip(), "dates": dates, "school": school})
    return entries


def _parse_skills(lines: list[str]) -> list[dict]:
    groups: list[dict] = []
    for line in lines:
        if ":" not in line:
            continue
        group, items = line.split(":", 1)
        group = group.replace("*", "").strip()
        if group and items.strip():
            groups.append({"id": new_id(), "group": group, "items": items.strip()})
    return groups


def _parse_plain_list(lines: list[str]) -> list[str]:
    return [item for item in (_clean_bullet(line) for line in lines) if item]


def _parse_languages(lines: list[str]) -> list[str]:
    languages: list[str] = []
    for line in lines:
        for part in re.split(r",|•", line):
            text = part.strip(" -*")
            if text:
                languages.append(text)
    return languages
