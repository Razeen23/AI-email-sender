from __future__ import annotations

import smtplib
from email.message import EmailMessage

from backend.textutil import clean_header


def _client(host: str, port: int):
    if port == 465:
        return smtplib.SMTP_SSL(host, port, timeout=30)
    smtp = smtplib.SMTP(host, port, timeout=30)
    try:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
    except Exception:
        smtp.close()
        raise
    return smtp


def check_login(*, host: str, port: int, username: str, password: str) -> None:
    try:
        with _client(host, port) as smtp:
            smtp.login(username, password)
    except (OSError, smtplib.SMTPException) as exc:
        raise ValueError("Could not sign in to that mailbox. Check the host, port, and app password.") from exc


def send_message(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    from_name: str,
    from_email: str,
    to_email: str,
    subject: str,
    body: str,
    attachment: tuple[str, bytes] | None,
) -> None:
    message = EmailMessage()
    sender = clean_header(from_email)
    name = clean_header(from_name)
    message["From"] = f"{name} <{sender}>" if name else sender
    message["To"] = clean_header(to_email)
    message["Subject"] = clean_header(subject)
    message.set_content(body)
    if attachment:
        filename, data = attachment
        subtype = "pdf"
        if filename.lower().endswith(".docx"):
            subtype = "vnd.openxmlformats-officedocument.wordprocessingml.document"
        message.add_attachment(data, maintype="application", subtype=subtype, filename=filename)
    try:
        with _client(host, port) as smtp:
            smtp.login(username, password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise ValueError("The mailbox rejected the message. Check the app password and from address.") from exc
