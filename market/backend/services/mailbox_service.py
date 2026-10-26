from __future__ import annotations

from backend.models.schemas import MailboxIn
from backend.repositories import mailbox_repo
from backend.security import decrypt_secret, encrypt_secret
from backend.services import email_service
from backend.textutil import clean_header, clip, valid_email

EMPTY = {
    "configured": False,
    "host": "",
    "port": 587,
    "username": "",
    "from_name": "",
    "from_email": "",
    "password_set": False,
}


def _public(row: dict | None) -> dict:
    if not row:
        return dict(EMPTY)
    return {
        "configured": True,
        "host": row["host"],
        "port": row["port"],
        "username": row["username"],
        "from_name": row["from_name"],
        "from_email": row["from_email"],
        "password_set": bool(row["password_encrypted"]),
    }


def get_mailbox(user_id: str) -> dict:
    return _public(mailbox_repo.get(user_id))


def _is_gmail_address(value: str) -> bool:
    lowered = value.lower()
    return lowered.endswith("@gmail.com") or lowered.endswith("@googlemail.com")


def _clean(body: MailboxIn) -> dict:
    host = clip(body.host, 200)
    username = clip(body.username, 254)
    from_email = clip(body.from_email, 254)
    password = "".join(body.password.split())
    if body.port < 1 or body.port > 65535:
        raise ValueError("Enter a port between 1 and 65535.")
    if not valid_email(from_email):
        raise ValueError("Enter a valid from address.")
    gmail = _is_gmail_address(host) or _is_gmail_address(from_email) or host.lower() in {"smtp.gmail.com", "smtp.googlemail.com"}
    if _is_gmail_address(host):
        if "@" not in username:
            username = host
        host = "smtp.gmail.com"
    elif gmail and ("@" in host or host.lower() in {"", "gmail", "gmail.com"}):
        host = "smtp.gmail.com"
    if gmail and "@" not in username:
        username = from_email
    port = body.port
    if host == "smtp.gmail.com" and port not in {465, 587}:
        port = 587
    if not host or not username:
        raise ValueError("Enter the mailbox host and username.")
    return {
        "host": host,
        "port": port,
        "username": username,
        "from_name": clean_header(clip(body.from_name, 120)),
        "from_email": from_email,
        "password": password,
        "gmail": gmail,
    }


def save(user_id: str, body: MailboxIn) -> dict:
    cleaned = _clean(body)
    existing = mailbox_repo.get(user_id)
    if cleaned["password"]:
        encrypted = encrypt_secret(cleaned["password"])
    elif existing:
        encrypted = existing["password_encrypted"]
    else:
        raise ValueError("Enter the mailbox password or app password.")
    mailbox_repo.upsert(
        user_id,
        host=cleaned["host"],
        port=cleaned["port"],
        username=cleaned["username"],
        from_name=cleaned["from_name"],
        from_email=cleaned["from_email"],
        password_encrypted=encrypted,
    )
    return get_mailbox(user_id)


def _password(user_id: str, typed: str) -> str:
    if typed:
        return typed
    existing = mailbox_repo.get(user_id)
    if not existing:
        raise ValueError("Enter the mailbox password or app password.")
    return decrypt_secret(existing["password_encrypted"])


def test_connection(user_id: str, body: MailboxIn) -> dict:
    cleaned = _clean(body)
    password = _password(user_id, cleaned["password"])
    try:
        email_service.check_login(
            host=cleaned["host"],
            port=cleaned["port"],
            username=cleaned["username"],
            password=password,
        )
    except ValueError as exc:
        if cleaned["gmail"]:
            raise ValueError(
                "Gmail refused the sign-in. The server is smtp.gmail.com, the username is the full Gmail address, and the password must be a Google app password."
            ) from exc
        raise
    body.host = cleaned["host"]
    body.port = cleaned["port"]
    body.username = cleaned["username"]
    body.password = password
    return save(user_id, body)


def credentials(user_id: str) -> dict:
    row = mailbox_repo.get(user_id)
    if not row:
        raise ValueError("Connect your mailbox before sending.")
    return {
        "host": row["host"],
        "port": row["port"],
        "username": row["username"],
        "from_name": row["from_name"],
        "from_email": row["from_email"],
        "password": decrypt_secret(row["password_encrypted"]),
    }


def require_ready(user_id: str) -> None:
    if not mailbox_repo.get(user_id):
        raise ValueError("Connect your mailbox before sending. A dry run does not need one.")
