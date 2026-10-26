from __future__ import annotations

from backend.clock import new_id
from backend.models.schemas import ProfileIn
from backend.repositories import profiles_repo
from backend.storage import base_resume_path
from backend.textutil import clip, valid_email


def _bullets(values: list[str]) -> list[str]:
    return [clip(item, 400) for item in values if item.strip()][:12]


def _entry_id(value: str) -> str:
    value = value.strip()
    return value if value else new_id()


def normalize(body: ProfileIn) -> dict:
    email = clip(body.email, 254)
    if email and not valid_email(email):
        raise ValueError("Enter a valid contact email on your profile.")
    skills = []
    for skill in body.skills[:30]:
        group = clip(skill.group, 80)
        items = clip(skill.items, 500)
        if not group and not items:
            continue
        skills.append({"id": _entry_id(skill.id), "group": group, "items": items})
    experience = []
    for item in body.experience[:25]:
        title = clip(item.title, 120)
        company = clip(item.company, 120)
        dates = clip(item.dates, 80)
        location = clip(item.location, 120)
        bullets = _bullets(item.bullets)
        if not any([title, company, dates, location, bullets]):
            continue
        experience.append(
            {
                "id": _entry_id(item.id),
                "title": title,
                "company": company,
                "dates": dates,
                "location": location,
                "bullets": bullets,
            }
        )
    projects = []
    for item in body.projects[:25]:
        name = clip(item.name, 120)
        tech = clip(item.tech, 200)
        bullets = _bullets(item.bullets)
        if not any([name, tech, bullets]):
            continue
        projects.append({"id": _entry_id(item.id), "name": name, "tech": tech, "bullets": bullets})
    education = []
    for item in body.education[:15]:
        degree = clip(item.degree, 160)
        school = clip(item.school, 160)
        dates = clip(item.dates, 80)
        if not any([degree, school, dates]):
            continue
        education.append({"id": _entry_id(item.id), "degree": degree, "school": school, "dates": dates})
    return {
        "name": clip(body.name, 120),
        "headline": clip(body.headline, 160),
        "email": email,
        "phone": clip(body.phone, 40),
        "city": clip(body.city, 80),
        "country": clip(body.country, 80),
        "linkedin": clip(body.linkedin, 200),
        "github": clip(body.github, 200),
        "portfolio": clip(body.portfolio, 200),
        "languages": [clip(item, 40) for item in body.languages if item.strip()][:12],
        "summary": clip(body.summary, 5000),
        "skills": skills,
        "experience": experience,
        "projects": projects,
        "education": education,
        "certifications": [clip(item, 160) for item in body.certifications if item.strip()][:20],
    }


def get_profile(user_id: str) -> dict:
    profile = profiles_repo.get(user_id)
    profile["has_base_resume"] = base_resume_path(user_id).exists()
    return profile


def save(user_id: str, body: ProfileIn) -> dict:
    profiles_repo.save(user_id, normalize(body))
    return get_profile(user_id)
