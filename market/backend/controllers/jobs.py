from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from backend.deps import require_user
from backend.models.schemas import JobIn, JobOut, PreviewIn, PreviewOut, ResumeChoiceIn, UploadOut
from backend.services import job_service, preview_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobOut])
def list_jobs(user: dict = Depends(require_user)):
    return job_service.list_jobs(user["id"])


@router.post("", response_model=JobOut)
def create_job(body: JobIn, user: dict = Depends(require_user)):
    try:
        return job_service.create(user["id"], body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{job_id}/resume", response_model=JobOut)
def set_job_resume(job_id: str, body: ResumeChoiceIn, user: dict = Depends(require_user)):
    if not body.resume_id.strip():
        raise HTTPException(status_code=400, detail="Choose a resume.")
    try:
        return job_service.assign_resume(user["id"], job_id, body.resume_id.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{job_id}")
def delete_job(job_id: str, user: dict = Depends(require_user)):
    try:
        job_service.delete(user["id"], job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@router.post("/upload", response_model=UploadOut)
async def upload_jobs(
    file: UploadFile = File(...),
    country_id: str = Form(""),
    user: dict = Depends(require_user),
):
    content = await file.read()
    try:
        return job_service.import_spreadsheet(user["id"], file.filename or "", content, country_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/preview", response_model=list[PreviewOut])
def preview_jobs(body: PreviewIn, user: dict = Depends(require_user)):
    try:
        return preview_service.preview(user["id"], body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
