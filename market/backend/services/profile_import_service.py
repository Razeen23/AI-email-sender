from __future__ import annotations

from backend.models.schemas import EducationIn, ExperienceIn, ProfileIn, ProjectIn, SkillIn
from backend.services import ai_service, document_service, profile_service


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item).strip() for item in value if str(item).strip())
    return str(value)


def _lines(value) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        return value.splitlines()
    return []


def _coerce(raw: dict) -> dict:
    skills = []
    for item in raw.get("skills") or []:
        if isinstance(item, str):
            skills.append({"group": "", "items": item})
        elif isinstance(item, dict):
            skills.append({"group": _text(item.get("group")), "items": _text(item.get("items"))})
    experience = []
    for item in raw.get("experience") or []:
        if not isinstance(item, dict):
            continue
        experience.append(
            {
                "title": _text(item.get("title")),
                "company": _text(item.get("company")),
                "dates": _text(item.get("dates")),
                "location": _text(item.get("location")),
                "bullets": _lines(item.get("bullets")),
            }
        )
    projects = []
    for item in raw.get("projects") or []:
        if not isinstance(item, dict):
            continue
        projects.append({"name": _text(item.get("name")), "tech": _text(item.get("tech")), "bullets": _lines(item.get("bullets"))})
    education = []
    for item in raw.get("education") or []:
        if not isinstance(item, dict):
            continue
        education.append({"degree": _text(item.get("degree")), "school": _text(item.get("school")), "dates": _text(item.get("dates"))})
    languages = raw.get("languages") or []
    if isinstance(languages, str):
        languages = [part.strip() for part in languages.split(",")]
    certifications = raw.get("certifications") or []
    if isinstance(certifications, str):
        certifications = certifications.splitlines()
    return {
        "name": _text(raw.get("name")),
        "headline": _text(raw.get("headline")),
        "email": _text(raw.get("email")),
        "phone": _text(raw.get("phone")),
        "city": _text(raw.get("city")),
        "country": _text(raw.get("country")),
        "linkedin": _text(raw.get("linkedin")),
        "github": _text(raw.get("github")),
        "portfolio": _text(raw.get("portfolio")),
        "languages": [str(item) for item in languages],
        "summary": _text(raw.get("summary")),
        "skills": skills,
        "experience": experience,
        "projects": projects,
        "education": education,
        "certifications": [str(item) for item in certifications],
    }


def draft_from_file(filename: str, content: bytes) -> dict:
    text = document_service.read_document(filename, content)
    filled_by = "model"
    try:
        raw = ai_service.extract_profile(text)
        if not isinstance(raw, dict):
            raise ValueError("The model did not return profile fields.")
    except ValueError:
        raw = document_service.fields_from_text(text)
        filled_by = "text"
    data = _coerce(raw)
    body = ProfileIn(
        name=data["name"],
        headline=data["headline"],
        email=data["email"],
        phone=data["phone"],
        city=data["city"],
        country=data["country"],
        linkedin=data["linkedin"],
        github=data["github"],
        portfolio=data["portfolio"],
        languages=data["languages"],
        summary=data["summary"],
        skills=[SkillIn(**item) for item in data["skills"]],
        experience=[ExperienceIn(**item) for item in data["experience"]],
        projects=[ProjectIn(**item) for item in data["projects"]],
        education=[EducationIn(**item) for item in data["education"]],
        certifications=data["certifications"],
    )
    try:
        draft = profile_service.normalize(body)
    except ValueError:
        body.email = ""
        draft = profile_service.normalize(body)
    draft["filled_by"] = filled_by
    return draft
