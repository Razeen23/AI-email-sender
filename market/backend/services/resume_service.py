from __future__ import annotations

import logging

from backend.services import ai_service
from backend.storage import (
    base_resume_path,
    generated_dir,
    generated_markdown_path,
    generated_name_path,
    generated_pdf_path,
    user_root,
)
from backend.textutil import slug

logger = logging.getLogger(__name__)

PDF_LIMIT = 8_000_000


def save_base(user_id: str, filename: str, content: bytes) -> str:
    if not filename.lower().endswith(".pdf") or not content.startswith(b"%PDF"):
        raise ValueError("Upload a PDF resume.")
    if len(content) > PDF_LIMIT:
        raise ValueError("Resume PDF must be under 8 MB.")
    folder = user_root(user_id)
    folder.mkdir(parents=True, exist_ok=True)
    base_resume_path(user_id).write_bytes(content)
    safe_name = filename.replace("\\", "/").split("/")[-1] or "resume.pdf"
    return safe_name


def delete_base(user_id: str) -> None:
    path = base_resume_path(user_id)
    if path.exists():
        path.unlink()


def _html(markdown_text: str) -> str:
    import markdown

    body = markdown.markdown(markdown_text, extensions=["extra"])
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><style>
body {{ font-family: Georgia, serif; font-size: 11pt; color: #111; line-height: 1.35; }}
h1 {{ font-size: 18pt; margin: 0 0 4px; }}
h2 {{ font-size: 12pt; margin: 14px 0 4px; border-bottom: 1px solid #ddd; }}
p, li {{ margin: 0 0 4px; }}
ul {{ margin: 0 0 6px 18px; }}
</style></head><body>{body}</body></html>"""


def generate(user_id: str, profile: dict, country: dict, job: dict) -> dict:
    markdown_text = ai_service.write_resume(profile=profile, country=country, job=job)
    folder = generated_dir(user_id)
    folder.mkdir(parents=True, exist_ok=True)
    generated_markdown_path(user_id, job["id"]).write_text(markdown_text, encoding="utf-8")
    filename = f"{slug(profile.get('name', ''))}-{slug(job.get('role', ''))}.pdf"
    generated_name_path(user_id, job["id"]).write_text(filename, encoding="utf-8")
    pdf_path = generated_pdf_path(user_id, job["id"])
    warning = ""
    pdf_ready = False
    try:
        from weasyprint import HTML

        HTML(string=_html(markdown_text)).write_pdf(pdf_path)
        pdf_ready = pdf_path.exists()
    except Exception as exc:
        logger.warning("PDF creation failed: %s", exc)
        warning = "The resume was saved as Markdown. A PDF could not be created on this machine."
        if pdf_path.exists():
            pdf_path.unlink()
    return {
        "markdown": markdown_text,
        "pdf_ready": pdf_ready,
        "filename": filename if pdf_ready else f"{job['id']}.md",
        "warning": warning,
    }


def _display_name(user_id: str, job_id: str, fallback: str) -> str:
    path = generated_name_path(user_id, job_id)
    if path.exists():
        name = path.read_text(encoding="utf-8").strip()
        if name:
            return name
    return fallback


def attachment(
    user_id: str,
    profile: dict,
    country: dict,
    job: dict,
    mode: str,
    resume_id: str = "",
) -> tuple[str, bytes] | None:
    if mode == "own":
        from backend.services import resume_library_service

        chosen = resume_library_service.resolve_id(user_id, country.get("id"), resume_id, job.get("resume_id"))
        return resume_library_service.attachment_for(user_id, chosen)
    if mode == "base":
        path = base_resume_path(user_id)
        if not path.exists():
            return None
        filename = profile.get("base_resume_filename") or "resume.pdf"
        return filename, path.read_bytes()
    if mode == "generated":
        pdf_path = generated_pdf_path(user_id, job["id"])
        if not pdf_path.exists():
            if generated_markdown_path(user_id, job["id"]).exists():
                return None
            generated = generate(user_id, profile, country, job)
            if not generated["pdf_ready"] or not pdf_path.exists():
                return None
        filename = _display_name(user_id, job["id"], "resume.pdf")
        return filename, pdf_path.read_bytes()
    raise ValueError("Choose one of your resumes or a generated resume.")
