from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from backend.deps import clear_session_cookie, require_user, set_session_cookie
from backend.models.schemas import LoginIn, RegisterIn, UserOut
from backend.security import SESSION_COOKIE
from backend.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut)
def register(body: RegisterIn, response: Response):
    try:
        user, token = auth_service.register(body.email, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    set_session_cookie(response, token)
    return user


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, response: Response):
    try:
        user, token = auth_service.login(body.email, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    set_session_cookie(response, token)
    return user


@router.post("/logout")
def logout(request: Request, response: Response):
    auth_service.logout(request.cookies.get(SESSION_COOKIE, ""))
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(require_user)):
    return user
