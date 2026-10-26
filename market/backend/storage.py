from __future__ import annotations

from pathlib import Path

from backend.paths import DATA_DIR
from backend.textutil import is_hex_id


def user_root(user_id: str) -> Path:
    if not is_hex_id(user_id):
        raise ValueError("Invalid account.")
    root = (DATA_DIR / "users").resolve()
    path = (root / user_id).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Invalid account.")
    return path


def base_resume_path(user_id: str) -> Path:
    return user_root(user_id) / "base.pdf"


def generated_dir(user_id: str) -> Path:
    return user_root(user_id) / "generated"


def generated_pdf_path(user_id: str, job_id: str) -> Path:
    if not is_hex_id(job_id):
        raise ValueError("Invalid job.")
    return generated_dir(user_id) / f"{job_id}.pdf"


def generated_markdown_path(user_id: str, job_id: str) -> Path:
    if not is_hex_id(job_id):
        raise ValueError("Invalid job.")
    return generated_dir(user_id) / f"{job_id}.md"


def generated_name_path(user_id: str, job_id: str) -> Path:
    if not is_hex_id(job_id):
        raise ValueError("Invalid job.")
    return generated_dir(user_id) / f"{job_id}.name"


def resume_library_dir(user_id: str) -> Path:
    return user_root(user_id) / "resumes"


def resume_file_path(user_id: str, resume_id: str, extension: str) -> Path:
    if not is_hex_id(resume_id) or extension not in {"pdf", "docx"}:
        raise ValueError("Invalid resume.")
    folder = resume_library_dir(user_id).resolve()
    path = (folder / f"{resume_id}.{extension}").resolve()
    if not path.is_relative_to(folder):
        raise ValueError("Invalid resume.")
    return path
