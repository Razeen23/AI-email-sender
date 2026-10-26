from __future__ import annotations

import uuid
from datetime import datetime, timedelta


def now_local() -> datetime:
    return datetime.now().astimezone()


def now_iso() -> str:
    return now_local().isoformat(timespec="seconds")


def today_start_iso() -> str:
    start = now_local().replace(hour=0, minute=0, second=0, microsecond=0)
    return start.isoformat(timespec="seconds")


def expires_iso(days: int) -> str:
    return (now_local() + timedelta(days=days)).isoformat(timespec="seconds")


def new_id() -> str:
    return uuid.uuid4().hex
