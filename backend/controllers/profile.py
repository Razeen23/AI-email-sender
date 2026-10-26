from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.models.schemas import ImportBaseRequest, ProfileDocument
from backend.services.profile_service import import_base_cvs, import_docx_file, load_profile_document, save_profile_document

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("")
def get_profile() -> dict:
    return load_profile_document()


@router.put("")
def put_profile(payload: ProfileDocument) -> dict:
    return save_profile_document(payload.model_dump())


@router.post("/import/base")
def import_base(payload: ImportBaseRequest) -> dict:
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="Confirm import before replacing the saved profile.")
    try:
        return import_base_cvs(save=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/import/docx")
async def import_docx(
    region: str = Form(...),
    confirm: str = Form(...),
    file: UploadFile = File(...),
) -> dict:
    if confirm.strip().lower() not in {"1", "true", "yes", "on"}:
        raise HTTPException(status_code=400, detail="Confirm import before replacing the saved profile.")
    filename = file.filename or "profile.docx"
    if Path(filename).suffix.lower() != ".docx":
        raise HTTPException(status_code=400, detail="Upload a .docx file.")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    existing = load_profile_document()
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as handle:
        handle.write(data)
        temp_path = Path(handle.name)
    try:
        return import_docx_file(temp_path, region, existing)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        temp_path.unlink(missing_ok=True)
