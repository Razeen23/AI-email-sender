from __future__ import annotations

import re

from backend.repositories import resumes_repo
from backend.services import country_service, profile_import_service
from backend.storage import resume_file_path, resume_library_dir

FILE_LIMIT = 8_000_000


def _display_name(filename: str, extension: str) -> str:
    name = filename.replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^\w.\- ()]+", "", name).strip() or f"resume.{extension}"
    if not name.lower().endswith(f".{extension}"):
        name = f"{name}.{extension}"
    return name[:180]


def _kind(filename: str, content: bytes) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf") and content.startswith(b"%PDF"):
        return "pdf"
    if lower.endswith(".docx") and content.startswith(b"PK"):
        return "docx"
    raise ValueError("Upload a PDF or a Word document (.docx).")


def list_resumes(user_id: str) -> list[dict]:
    return resumes_repo.list_for_user(user_id)


def default_resume_id(user_id: str, country_id: str | None) -> str | None:
    if not country_id:
        return None
    for resume in resumes_repo.list_for_country(user_id, country_id):
        if resume["is_default"]:
            return resume["id"]
    return None


def upload(user_id: str, country_id: str, filename: str, content: bytes) -> dict:
    if len(content) > FILE_LIMIT:
        raise ValueError("Resume must be under 8 MB.")
    country_service.require(user_id, country_id)
    extension = _kind(filename, content)
    existing = resumes_repo.list_for_country(user_id, country_id)
    is_default = not any(item["is_default"] for item in existing)
    saved = resumes_repo.create(
        user_id,
        country_id=country_id,
        filename=_display_name(filename or f"resume.{extension}", extension),
        extension=extension,
        is_default=is_default,
    )
    folder = resume_library_dir(user_id)
    folder.mkdir(parents=True, exist_ok=True)
    resume_file_path(user_id, saved["id"], extension).write_bytes(content)
    return saved


def make_default(user_id: str, resume_id: str) -> dict:
    resume = resumes_repo.get(user_id, resume_id)
    if not resume:
        raise ValueError("That resume is not on your account.")
    resumes_repo.set_default(user_id, resume["country_id"], resume_id)
    updated = resumes_repo.get(user_id, resume_id)
    if not updated:
        raise ValueError("That resume is not on your account.")
    return updated


def delete(user_id: str, resume_id: str) -> None:
    resume = resumes_repo.get(user_id, resume_id)
    if not resume:
        raise ValueError("That resume is not on your account.")
    path = resume_file_path(user_id, resume_id, resume["extension"])
    resumes_repo.delete(user_id, resume_id)
    if path.exists():
        path.unlink()
    if resume["is_default"]:
        remaining = resumes_repo.list_for_country(user_id, resume["country_id"])
        if remaining:
            resumes_repo.set_default(user_id, resume["country_id"], remaining[-1]["id"])


def delete_for_country(user_id: str, country_id: str) -> None:
    rows = resumes_repo.clear_for_country(user_id, country_id)
    for row in rows:
        path = resume_file_path(user_id, row["id"], row["extension"])
        if path.exists():
            path.unlink()


def file_for_download(user_id: str, resume_id: str):
    resume = resumes_repo.get(user_id, resume_id)
    if not resume:
        raise ValueError("That resume is not on your account.")
    path = resume_file_path(user_id, resume_id, resume["extension"])
    if not path.exists():
        raise ValueError("That resume file is missing.")
    media = (
        "application/pdf"
        if resume["extension"] == "pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    return path, resume["filename"], media


def attachment_for(user_id: str, resume_id: str) -> tuple[str, bytes]:
    resume = resumes_repo.get(user_id, resume_id)
    if not resume:
        raise ValueError("Choose a resume from this country.")
    path = resume_file_path(user_id, resume_id, resume["extension"])
    if not path.exists():
        raise ValueError("That resume file is missing.")
    return resume["filename"], path.read_bytes()


def resolve_id(user_id: str, country_id: str | None, resume_id: str, job_resume_id: str | None) -> str:
    chosen = (resume_id or job_resume_id or "").strip()
    if chosen:
        resume = resumes_repo.get(user_id, chosen)
        if not resume:
            raise ValueError("Choose a resume from this country.")
        if country_id and resume["country_id"] != country_id:
            raise ValueError("Choose a resume from this country.")
        return chosen
    fallback = default_resume_id(user_id, country_id)
    if not fallback:
        raise ValueError("Upload a resume for this country, or generate one instead.")
    return fallback


def fill_profile(user_id: str, resume_id: str) -> dict:
    resume = resumes_repo.get(user_id, resume_id)
    if not resume:
        raise ValueError("That resume is not on your account.")
    path = resume_file_path(user_id, resume_id, resume["extension"])
    if not path.exists():
        raise ValueError("That resume file is missing.")
    return profile_import_service.draft_from_file(resume["filename"], path.read_bytes())
