from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from backend.models.schemas import GenerateResumeRequest
from backend.services.resume_service import delete_resume, generate_resume_for_row, list_resumes, open_resume_file

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.get("")
def resumes(region: str | None = Query(default=None)) -> dict:
    try:
        return list_resumes(region)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/file")
def resume_file(path: str = Query(...)) -> Response:
    try:
        resolved = open_resume_file(path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        content=resolved.read_bytes(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": "inline",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router.delete("")
def remove_resume(path: str = Query(...)) -> dict:
    try:
        return delete_resume(path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/generate")
def generate(payload: GenerateResumeRequest) -> dict:
    try:
        return generate_resume_for_row(
            company=payload.company,
            role=payload.role,
            region=payload.region,
            job_description=payload.job_description,
            overwrite=payload.overwrite,
            source_paths=payload.source_paths,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
