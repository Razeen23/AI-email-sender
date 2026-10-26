from __future__ import annotations

import json
import logging

import requests

from backend.paths import ollama_base_url, ollama_model
from backend.textutil import clean_header, clip

logger = logging.getLogger(__name__)


def reachable() -> bool:
    try:
        response = requests.get(f"{ollama_base_url()}/api/tags", timeout=2)
        return response.ok
    except requests.RequestException:
        return False


def _facts(profile: dict, country: dict) -> dict:
    phone = country.get("phone", "").strip() or profile.get("phone", "")
    location = country.get("location_line", "").strip()
    if not location:
        location = ", ".join(part for part in (profile.get("city", ""), profile.get("country", "")) if part)
    return {
        "name": profile.get("name", ""),
        "headline": profile.get("headline", ""),
        "email": profile.get("email", ""),
        "phone": phone,
        "location_line": location,
        "target_country": country.get("label", ""),
        "links": {
            "linkedin": profile.get("linkedin", ""),
            "github": profile.get("github", ""),
            "portfolio": profile.get("portfolio", ""),
        },
        "languages": profile.get("languages", []),
        "summary": profile.get("summary", ""),
        "skills": profile.get("skills", []),
        "experience": profile.get("experience", []),
        "projects": profile.get("projects", []),
        "education": profile.get("education", []),
        "certifications": profile.get("certifications", []),
    }


def _generate(prompt: str, limit: int) -> str:
    try:
        response = requests.post(
            f"{ollama_base_url()}/api/generate",
            json={
                "model": ollama_model(),
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": limit},
            },
            timeout=180,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Ollama request failed: %s", exc)
        raise ValueError("Ollama is not reachable. Start it on this machine and check the model name.") from exc
    text = str(response.json().get("response", "")).strip()
    if not text:
        raise ValueError("Ollama returned an empty response.")
    return text


def _strip_fences(text: str) -> str:
    cleaned = text.strip()
    if not cleaned.startswith("```"):
        return cleaned
    lines = cleaned.splitlines()[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _job_brief(job: dict) -> str:
    role = str(job.get("role", "")).strip()
    company = str(job.get("company", "")).strip()
    if role:
        purpose = f"This is an application for the role {role}"
        purpose += f" at {company}." if company else "."
    else:
        purpose = "There is no role title. Write a short cold email. Do not invent a job title."
        if company:
            purpose += f" The company is {company}."
    skills = str(job.get("skills", "")).strip()
    skills_line = f"Skills named on this lead: {skills}" if skills else "No extra skills were supplied for this lead."
    return f"{purpose}\n{skills_line}"


def write_email(*, profile: dict, country: dict, job: dict) -> dict:
    referral = job.get("referral_name", "").strip()
    referral_line = (
        f"The applicant was referred by {referral}. Mention that once, in the first lines."
        if referral
        else "There is no referral."
    )
    prompt = f"""
You write an email for a job seeker. Use ONLY facts in the profile JSON.
Do not invent employers, dates, skills, degrees, metrics, visas, or tools.
If the job asks for something missing from the profile, do not claim it.
{referral_line}
{_job_brief(job)}
The person is writing from {country.get("label", "")}.
Return JSON only, with keys "subject" and "body".
The body is plain text, under 180 words, with a greeting and the person's name at the end.
No markdown.

Profile:
{json.dumps(_facts(profile, country), ensure_ascii=False)}

Company: {job.get("company", "")}
Role: {job.get("role", "")}
Job description:
{clip(job.get("job_description", ""), 6000)}
""".strip()
    raw = _strip_fences(_generate(prompt, 900))
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("The model did not return an email subject and body.")
    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError("The model did not return an email subject and body.") from exc
    subject = clean_header(str(data.get("subject", "")))
    body = str(data.get("body", "")).strip()
    if not subject or not body:
        raise ValueError("The model did not return an email subject and body.")
    return {"subject": clip(subject, 150), "body": clip(body, 5000)}


def write_resume(*, profile: dict, country: dict, job: dict) -> str:
    prompt = f"""
Write a tailored resume in Markdown. Use ONLY facts in the profile JSON.
Do not invent employers, dates, skills, degrees, metrics, or tools.
If there is no role title, keep the profile's own headline and do not invent a target job.
Keep bullets that match the role when one is given. Drop facts that are not relevant, but do not rewrite them into new claims.
Header: name as h1, then headline, email, phone, location line, and links.
Then sections that have content: Summary, Skills, Experience, Projects, Education, Certifications.
Mention the target role and company only if it fits a summary sentence grounded in the profile.
Return Markdown only.

Target country: {country.get("label", "")}
Company: {job.get("company", "")}
Role: {job.get("role", "")}
Job description:
{clip(job.get("job_description", ""), 6000)}

Profile:
{json.dumps(_facts(profile, country), ensure_ascii=False)}
""".strip()
    text = _strip_fences(_generate(prompt, 1800))
    if not text:
        raise ValueError("The model did not return a resume.")
    return text


def extract_profile(text: str) -> dict:
    prompt = f"""
Extract this person's own career facts from the document.
Return JSON only with keys:
name, headline, email, phone, city, country, linkedin, github, portfolio,
languages (array of strings), summary,
skills (array of objects with group and items),
experience (array of objects with title, company, dates, location, bullets),
projects (array of objects with name, tech, bullets),
education (array of objects with degree, school, dates),
certifications (array of strings).
Use empty strings or empty arrays when a fact is not in the document.
Do not invent employers, dates, skills, degrees, or contact details.

Document:
{clip(text, 14000)}
""".strip()
    raw = _strip_fences(_generate(prompt, 1800))
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("The model did not return profile fields.")
    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError("The model did not return profile fields.") from exc
    if not isinstance(data, dict):
        raise ValueError("The model did not return profile fields.")
    return data
