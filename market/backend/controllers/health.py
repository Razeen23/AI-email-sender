from __future__ import annotations

from fastapi import APIRouter

from backend.db import db_path
from backend.models.schemas import HealthOut
from backend.paths import ollama_base_url, ollama_model
from backend.services import ai_service

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthOut)
def health():
    return {
        "ollama_reachable": ai_service.reachable(),
        "ollama_base_url": ollama_base_url(),
        "ollama_model": ollama_model(),
        "db_exists": db_path().exists(),
    }
