"""
Pick resumes/INR|UAE/<folder> PDF by role. Gen-AI CV is used when role OR job description
(or key skills / why match for send_emails2) mention AI-related terms—so a generic title
like "Software Engineer" still gets gen-ai if the JD is about LLM/RAG/etc.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

# Non-AI: match Role column only (JD may mention "React" without meaning react-js resume).
ROLE_TO_FOLDER = [
    (re.compile(r"frontend|front\s*end", re.I), "front-end"),
    (re.compile(r"full\s*stack|fullstack", re.I), "full-stack"),
    (re.compile(r"react\s*js|react", re.I), "react-js"),
]
DEFAULT_FOLDER = "full-stack"

# Combined text (role + JD + optional columns): if any matches, attach gen-ai PDF.
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


def role_to_resume_subdir(
    role: str,
    region: str,
    *,
    job_description: str | None = None,
    key_skills: str | None = None,
    why_match: str | None = None,
) -> str:
    """Folder name under resumes/INR or resumes/UAE (actual disk layout)."""
    reg = (region or "").strip().upper()
    if should_use_gen_ai_resume(role, job_description, key_skills, why_match):
        return "gen-ai-uae" if reg == "UAE" else "gen-ai"
    r = (role or "").strip().lower()
    for pattern, folder in ROLE_TO_FOLDER:
        if pattern.search(r):
            return f"{folder}-{reg.lower()}"
    return f"{DEFAULT_FOLDER}-{reg.lower()}"


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
    """Pick resume from resumes/INR or resumes/UAE. Do not use generated/."""
    folder_name = role_to_resume_subdir(
        role,
        region,
        job_description=job_description,
        key_skills=key_skills,
        why_match=why_match,
    )
    dir_path = Path(resumes_base) / region / folder_name
    if not dir_path.is_dir():
        default_resume = (
            Path(resumes_base) / "INR" / "full-stack-inr" / "Full-stack-developer-CV-Razeen.pdf"
            if region == "INR"
            else Path(resumes_base) / "UAE" / "full-stack-uae" / "Full-stack-developer-CV-Razeen.pdf"
        )
        if default_resume.is_file():
            logger.warning("Resume directory not found: %s. Falling back to %s", dir_path, default_resume)
            return str(default_resume)
        logger.error("Resume directory not found: %s (and default resume missing at %s)", dir_path, default_resume)
        return None
    pdfs = sorted(
        [f for f in dir_path.iterdir() if f.suffix.lower() == ".pdf" and ".." not in f.name],
        key=lambda p: p.name,
    )
    if not pdfs:
        default_resume = (
            Path(resumes_base) / "INR" / "full-stack-inr" / "Full-stack-developer-CV-Razeen.pdf"
            if region == "INR"
            else Path(resumes_base) / "UAE" / "full-stack-uae" / "Full-stack-developer-CV-Razeen.pdf"
        )
        if default_resume.is_file():
            logger.warning("No PDF found in %s. Falling back to %s", dir_path, default_resume)
            return str(default_resume)
        logger.error("No PDF found in %s (and default resume missing at %s)", dir_path, default_resume)
        return None
    return str(pdfs[0])
