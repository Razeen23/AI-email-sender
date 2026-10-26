from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.deps import require_user
from backend.models.schemas import ProfileDraftOut, ResumeOut
from backend.repositories import profiles_repo
from backend.services import resume_library_service
from backend.storage import base_resume_path, generated_name_path, generated_pdf_path

router = APIRouter(prefix="/resumes", tags=["resumes"])


def _pdf(path, filename: str) -> FileResponse:
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=filename,
        content_disposition_type="inline",
    )


@router.get("", response_model=list[ResumeOut])
def list_resumes(user: dict = Depends(require_user)):
    return resume_library_service.list_resumes(user["id"])


@router.post("", response_model=ResumeOut)
async def upload_resume(
    country_id: str = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(require_user),
):
    content = await file.read()
    try:
        return resume_library_service.upload(user["id"], country_id, file.filename or "", content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{resume_id}/default", response_model=ResumeOut)
def make_default(resume_id: str, user: dict = Depends(require_user)):
    try:
        return resume_library_service.make_default(user["id"], resume_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{resume_id}")
def delete_resume(resume_id: str, user: dict = Depends(require_user)):
    try:
        resume_library_service.delete(user["id"], resume_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@router.get("/file/{resume_id}")
def download_resume(resume_id: str, user: dict = Depends(require_user)):
    try:
        path, filename, media = resume_library_service.file_for_download(user["id"], resume_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Resume not found.") from exc
    disposition = "inline" if filename.lower().endswith(".pdf") else "attachment"
    return FileResponse(path, media_type=media, filename=filename, content_disposition_type=disposition)


@router.post("/{resume_id}/fill", response_model=ProfileDraftOut)
def fill_from_resume(resume_id: str, user: dict = Depends(require_user)):
    try:
        return resume_library_service.fill_profile(user["id"], resume_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/base")
def download_base(user: dict = Depends(require_user)):
    path = base_resume_path(user["id"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Upload a base resume first.")
    profile = profiles_repo.get(user["id"])
    return _pdf(path, profile["base_resume_filename"] or "resume.pdf")


@router.get("/generated/{job_id}")
def download_generated(job_id: str, user: dict = Depends(require_user)):
    try:
        path = generated_pdf_path(user["id"], job_id)
        name_path = generated_name_path(user["id"], job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Resume not found.") from exc
    if not path.exists():
        raise HTTPException(status_code=404, detail="Resume not found.")
    filename = name_path.read_text(encoding="utf-8").strip() if name_path.exists() else "resume.pdf"
    return _pdf(path, filename or "resume.pdf")
