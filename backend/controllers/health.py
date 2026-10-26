from fastapi import APIRouter

from backend.services.health_service import get_health

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return get_health()
