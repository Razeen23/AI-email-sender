from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.deps import require_user
from backend.models.schemas import RunOut, SendIn, SendRowOut
from backend.services import send_service, stats_service
from backend.services.send_service import JobBusyError

router = APIRouter(prefix="/sends", tags=["sends"])


@router.get("", response_model=list[SendRowOut])
def history(user: dict = Depends(require_user)):
    return stats_service.history(user["id"])


@router.post("", response_model=RunOut)
def start_send(body: SendIn, user: dict = Depends(require_user)):
    try:
        return send_service.runner.start(user["id"], body)
    except JobBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: str, user: dict = Depends(require_user)):
    try:
        return send_service.runner.get(user["id"], run_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
