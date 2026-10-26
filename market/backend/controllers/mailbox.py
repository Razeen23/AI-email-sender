from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.deps import require_user
from backend.models.schemas import MailboxIn, MailboxOut
from backend.services import mailbox_service

router = APIRouter(prefix="/mailbox", tags=["mailbox"])


@router.get("", response_model=MailboxOut)
def get_mailbox(user: dict = Depends(require_user)):
    return mailbox_service.get_mailbox(user["id"])


@router.put("", response_model=MailboxOut)
def save_mailbox(body: MailboxIn, user: dict = Depends(require_user)):
    try:
        return mailbox_service.save(user["id"], body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/test", response_model=MailboxOut)
def test_mailbox(body: MailboxIn, user: dict = Depends(require_user)):
    try:
        return mailbox_service.test_connection(user["id"], body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
