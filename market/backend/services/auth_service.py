from __future__ import annotations

from backend.repositories import sessions_repo, users_repo
from backend.security import hash_password, verify_password
from backend.textutil import valid_email


def register(email: str, password: str) -> tuple[dict, str]:
    cleaned = email.strip().lower()
    if not valid_email(cleaned):
        raise ValueError("Enter a valid email address.")
    if users_repo.get_by_email(cleaned):
        raise ValueError("An account with that email already exists.")
    user = users_repo.create(cleaned, hash_password(password))
    token = sessions_repo.create(user["id"])
    return user, token


def login(email: str, password: str) -> tuple[dict, str]:
    cleaned = email.strip().lower()
    row = users_repo.get_by_email(cleaned)
    if not row or not verify_password(password, row["password_hash"]):
        raise ValueError("Email or password is incorrect.")
    token = sessions_repo.create(row["id"])
    return users_repo.public_user(row), token


def logout(token: str) -> None:
    sessions_repo.delete(token)


def current(token: str) -> dict | None:
    return sessions_repo.user_for_token(token)
