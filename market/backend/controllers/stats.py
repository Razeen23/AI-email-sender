from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.deps import require_user
from backend.models.schemas import StatsOut
from backend.services import stats_service

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("", response_model=StatsOut)
def stats(user: dict = Depends(require_user)):
    return stats_service.stats(user["id"])
