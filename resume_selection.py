"""
Pick a PDF from resumes/INR-CV's or resumes/UAE-CV's by role (and JD/skills for Gen-AI).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

REGION_FOLDERS = {
    "INR": "INR-CV's",
    "UAE": "UAE-CV's",
}

ROLE_TO_STEM = [
    (re.compile(r"front[\s-]*end|frontend", re.I), "Front-End-Developer"),
    (re.compile(r"react", re.I), "React-JS-Developer"),
    (re.compile(r"backend|back[\s-]*end", re.I), "Backend-Developer"),
    (re.compile(r"devops|dev[\s-]*ops|\bsre\b", re.I), "DevOps-Engineer"),
    (re.compile(r"platform", re.I), "Platform-Engineer"),
    (re.compile(r"integration", re.I), "Integration-Engineer"),
    (re.compile(r"saas|product\s*engineer", re.I), "SaaS-Product-Engineer"),
    (re.compile(r"full[\s-]*stack|fullstack", re.I), "AI-Full-Stack-Developer"),
]
DEFAULT_STEM = "AI-Full-Stack-Developer"

GEN_AI_RESUME_PATTERN = re.compile(
    r"""
    \bgenai\b
    | gen\s*[- ]?ai
    | generative\s*ai
    | \bai\s*/\s*ml\b
    | \bai/ml\b
    | \bllm\b
    | large\s*language
    | artificial\s*intelligence
    | \bai\s*(engineer|developer|scientist|specialist|architect)\b
    | langchain
    | prompt\s*engineer
    | \brag\b
    | vector\s*(db|database|store)?
    | embedding
    | machine\s*learning
    | \bml\s+engineer\b
    | \bnlp\b
    | natural\s*language
    | deep\s*learning
    | (?<![a-z0-9])ai(?![a-z0-9])
    """,
    re.I | re.VERBOSE,
)


def region_resume_dir(resumes_base: str | Path, region: str) -> Path:
    key = (region or "").strip().upper()
    return Path(resumes_base) / REGION_FOLDERS.get(key, REGION_FOLDERS["INR"])


def _combined_context(
    role: str | None,
    job_description: str | None = None,
    key_skills: str | None = None,
    why_match: str | None = None,
) -> str:
    parts = [role or "", job_description or "", key_skills or "", why_match or ""]
    return " ".join(p.strip() for p in parts if p and str(p).strip())


def should_use_gen_ai_resume(
    role: str | None,
    job_description: str | None = None,
    key_skills: str | None = None,
    why_match: str | None = None,
) -> bool:
    text = _combined_context(role, job_description, key_skills, why_match)
    if not text.strip():
        return False
    return bool(GEN_AI_RESUME_PATTERN.search(text))


def _compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def role_to_resume_stem(
    role: str,
    *,
    job_description: str | None = None,
    key_skills: str | None = None,
    why_match: str | None = None,
) -> str:
    r = (role or "").strip()
    if not r or r.lower() == "nan":
        return DEFAULT_STEM
    if should_use_gen_ai_resume(role, job_description, key_skills, why_match):
        return "Generative-AI-Engineer"
    for pattern, stem in ROLE_TO_STEM:
        if pattern.search(r):
            return stem
    return DEFAULT_STEM


def _iter_pdfs(dir_path: Path) -> list[Path]:
    if not dir_path.is_dir():
        return []
    return sorted(
        [f for f in dir_path.iterdir() if f.suffix.lower() == ".pdf" and not f.name.startswith("~$") and ".." not in f.name],
        key=lambda p: p.name,
    )


def _find_pdf_by_stem(dir_path: Path, stem: str) -> Path | None:
    needle = _compact(stem)
    for pdf in _iter_pdfs(dir_path):
        if needle and needle in _compact(pdf.stem):
            return pdf
    return None


def role_to_resume_subdir(
    role: str,
    region: str,
    *,
    job_description: str | None = None,
    key_skills: str | None = None,
    why_match: str | None = None,
) -> str:
    """Region folder name on disk (kept for callers that still expect a subdir)."""
    key = (region or "").strip().upper()
    return REGION_FOLDERS.get(key, REGION_FOLDERS["INR"])


def get_resume_path(
    resumes_base: str,
    region: str,
    role: str,
    logger: logging.Logger,
    *,
    job_description: str | None = None,
    key_skills: str | None = None,
    why_match: str | None = None,
) -> str | None:
    """Pick a stock PDF from resumes/INR-CV's or resumes/UAE-CV's. Do not use generated/."""
    dir_path = region_resume_dir(resumes_base, region)
    stem = role_to_resume_stem(
        role,
        job_description=job_description,
        key_skills=key_skills,
        why_match=why_match,
    )
    chosen = _find_pdf_by_stem(dir_path, stem)
    if chosen:
        return str(chosen)

    fallback = _find_pdf_by_stem(dir_path, DEFAULT_STEM)
    if fallback:
        logger.warning("No %s resume in %s. Falling back to %s", stem, dir_path, fallback.name)
        return str(fallback)

    pdfs = _iter_pdfs(dir_path)
    if pdfs:
        logger.warning("No matching resume in %s. Falling back to %s", dir_path, pdfs[0].name)
        return str(pdfs[0])

    logger.error("Resume directory empty or missing: %s", dir_path)
    return None
