from __future__ import annotations

import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
HEX_ID_RE = re.compile(r"^[a-f0-9]{32}$")


def clip(value: str, limit: int) -> str:
    return value.strip()[:limit]


def norm_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def valid_email(value: str) -> bool:
    return bool(EMAIL_RE.match(value.strip()))


def clean_header(value: str) -> str:
    return re.sub(r"[\r\n]+", " ", value).strip()


def slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return text[:80] or "resume"


def is_hex_id(value: str) -> bool:
    return bool(HEX_ID_RE.fullmatch(value))
