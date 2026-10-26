from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from backend.deps import require_user
from backend.models.schemas import ProfileDraftOut, ProfileIn, ProfileOut
from backend.repositories import profiles_repo
from backend.services import profile_import_service, profile_service, resume_service

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=ProfileOut)
def get_profile(user: dict = Depends(require_user)):
    return profile_service.get_profile(user["id"])


@router.put("", response_model=ProfileOut)
def save_profile(body: ProfileIn, user: dict = Depends(require_user)):
    try:
        return profile_service.save(user["id"], body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/import", response_model=ProfileDraftOut)
async def import_profile(file: UploadFile = File(...), user: dict = Depends(require_user)):
    content = await file.read()
    try:
        return profile_import_service.draft_from_file(file.filename or "", content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/resume", response_model=ProfileOut)
async def upload_resume(file: UploadFile = File(...), user: dict = Depends(require_user)):
    content = await file.read()
    try:
        filename = resume_service.save_base(user["id"], file.filename or "resume.pdf", content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    profiles_repo.set_base_filename(user["id"], filename)
    return profile_service.get_profile(user["id"])


@router.delete("/resume", response_model=ProfileOut)
def delete_resume(user: dict = Depends(require_user)):
    resume_service.delete_base(user["id"])
    profiles_repo.set_base_filename(user["id"], "")
    return profile_service.get_profile(user["id"])
