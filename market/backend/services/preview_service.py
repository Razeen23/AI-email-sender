from __future__ import annotations

from backend.models.schemas import PreviewIn
from backend.repositories import jobs_repo
from backend.services import ai_service, country_service, profile_service, resume_service

PREVIEW_LIMIT = 8


def _row(job_id: str, **kwargs) -> dict:
    base = {
        "job_id": job_id,
        "company": "",
        "role": "",
        "contact_email": "",
        "country_label": "",
        "subject": "",
        "body": "",
        "resume_id": "",
        "resume_filename": "",
        "pdf_ready": False,
        "markdown": "",
        "warning": "",
        "error": "",
    }
    base.update(kwargs)
    return base


def preview(user_id: str, body: PreviewIn) -> list[dict]:
    if not body.job_ids:
        raise ValueError("Select at least one job.")
    if len(body.job_ids) > PREVIEW_LIMIT:
        raise ValueError(f"Preview up to {PREVIEW_LIMIT} jobs at a time.")
    profile = profile_service.get_profile(user_id)
    if not profile["name"].strip():
        raise ValueError("Add your name on the Profile page before previewing.")
    if body.resume_mode == "base" and not profile["has_base_resume"]:
        raise ValueError("Upload a resume for this country, or generate one.")
    if body.country_id:
        country_service.require(user_id, body.country_id)
    results = []
    for job_id in body.job_ids:
        job = jobs_repo.get(user_id, job_id)
        if not job:
            results.append(_row(job_id, error="That job is not on your list. It was removed when a newer spreadsheet replaced the list."))
            continue
        chosen = job["country_id"] or body.country_id
        if not chosen:
            results.append(
                _row(
                    job_id,
                    company=job["company"],
                    role=job["role"],
                    contact_email=job["contact_email"],
                    error="Choose a target country for this job.",
                )
            )
            continue
        try:
            country = country_service.require(user_id, chosen)
        except ValueError as exc:
            results.append(_row(job_id, company=job["company"], role=job["role"], error=str(exc)))
            continue
        try:
            warning = ""
            markdown = ""
            resume_id = ""
            pdf_ready = body.resume_mode == "base"
            filename = profile["base_resume_filename"] if body.resume_mode == "base" else ""
            if body.resume_mode == "own":
                from backend.services import resume_library_service

                resume_id = resume_library_service.resolve_id(user_id, country["id"], "", job.get("resume_id"))
                filename, _data = resume_library_service.attachment_for(user_id, resume_id)
                pdf_ready = filename.lower().endswith(".pdf")
            email = ai_service.write_email(profile=profile, country=country, job=job)
            if body.resume_mode == "generated":
                generated = resume_service.generate(user_id, profile, country, job)
                markdown = generated["markdown"]
                pdf_ready = generated["pdf_ready"]
                filename = generated["filename"]
                warning = generated["warning"]
            results.append(
                _row(
                    job_id,
                    company=job["company"],
                    role=job["role"],
                    contact_email=job["contact_email"],
                    country_label=country["label"],
                    subject=email["subject"],
                    body=email["body"],
                    resume_id=resume_id,
                    resume_filename=filename,
                    pdf_ready=pdf_ready,
                    markdown=markdown,
                    warning=warning,
                )
            )
        except ValueError as exc:
            results.append(
                _row(
                    job_id,
                    company=job["company"],
                    role=job["role"],
                    contact_email=job["contact_email"],
                    country_label=country["label"],
                    error=str(exc),
                )
            )
    return results
