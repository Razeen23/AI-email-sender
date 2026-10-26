from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from backend.services.excel_service import list_excel_files, preview_excel, save_upload

router = APIRouter(prefix="/excel", tags=["excel"])


@router.get("")
def list_files() -> dict:
    return {"files": list_excel_files()}


@router.post("/upload")
async def upload_excel(region: str = Form(...), file: UploadFile = File(...)) -> dict:
    filename = file.filename or "upload.xlsx"
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    try:
        return save_upload(filename, data, region)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/preview")
def preview(path: str = Query(...), region: str | None = None) -> dict:
    try:
        return preview_excel(path, region)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
