from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.models.schemas import SingleEmailRequest, SingleSendRequest
from backend.services.single_service import draft_single, send_single, suggest_single

router = APIRouter(prefix="/single", tags=["single"])


@router.post("/suggest")
def suggest(payload: SingleEmailRequest) -> dict:
    try:
        return suggest_single(
            email=payload.email,
            role=payload.role,
            skills=payload.skills,
            job_description=payload.job_description,
            region=payload.region,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/draft")
def draft(payload: SingleEmailRequest) -> dict:
    try:
        return draft_single(
            email=payload.email,
            role=payload.role,
            skills=payload.skills,
            job_description=payload.job_description,
            region=payload.region,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/send")
def send(payload: SingleSendRequest) -> dict:
    try:
        return send_single(
            email=payload.email,
            role=payload.role,
            skills=payload.skills,
            job_description=payload.job_description,
            region=payload.region,
            resume_path=payload.resume_path,
            subject=payload.subject,
            body=payload.body,
            dry_run=payload.dry_run,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
