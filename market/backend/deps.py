from __future__ import annotations

from fastapi import HTTPException, Request, Response

from backend.repositories import sessions_repo
from backend.security import SESSION_COOKIE, SESSION_DAYS


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def require_user(request: Request) -> dict:
    token = request.cookies.get(SESSION_COOKIE, "")
    user = sessions_repo.user_for_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Sign in required.")
    return user


def raise_value(exc: ValueError) -> None:
    raise HTTPException(status_code=400, detail=str(exc)) from exc
