from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.deps import require_user
from backend.models.schemas import CountryIn, CountryOut
from backend.services import country_service

router = APIRouter(prefix="/countries", tags=["countries"])


@router.get("", response_model=list[CountryOut])
def list_countries(user: dict = Depends(require_user)):
    return country_service.list_countries(user["id"])


@router.post("", response_model=CountryOut)
def create_country(body: CountryIn, user: dict = Depends(require_user)):
    try:
        return country_service.create(user["id"], body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{country_id}", response_model=CountryOut)
def update_country(country_id: str, body: CountryIn, user: dict = Depends(require_user)):
    try:
        return country_service.update(user["id"], country_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{country_id}")
def delete_country(country_id: str, user: dict = Depends(require_user)):
    try:
        country_service.delete(user["id"], country_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}
