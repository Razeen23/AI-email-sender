"""
SQLite logging for email send attempts. One table per entry script; see TABLE_* constants.

Env:
  EMAIL_SENDS_DB — path (default data/email_sends.db)
  EMAIL_SENDS_LOG=0 — disable inserts
  EMAIL_DEDUP=0 — skip same-job/email deduplication (default on)
  EMAIL_DEDUP_DAYS — window for dedup (default 15)
"""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

TABLE_SEND_EMAILS2 = "sends_send_emails2"
TABLE_SEND_EMAILS = "sends_send_emails"
TABLE_SEND_GENERATED_RESUME_EMAIL = "sends_send_generated_resume_email"
TABLE_GENERATE_RESUME = "sends_generate_resume"

ALLOWED_TABLES = frozenset(
    {
        TABLE_SEND_EMAILS2,
        TABLE_SEND_EMAILS,
        TABLE_SEND_GENERATED_RESUME_EMAIL,
        TABLE_GENERATE_RESUME,
    }
)

_CREATE_COLUMNS = """
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    recipient_email TEXT NOT NULL,
    success INTEGER NOT NULL,
    dry_run INTEGER NOT NULL DEFAULT 0,
    company TEXT,
    role TEXT,
    region TEXT,
    subject TEXT,
    pdf_path TEXT,
    pdf_filename TEXT,
    excel_path TEXT,
    failure_reason TEXT
"""

_INDEX_SUFFIXES = ("created_at", "recipient_email", "success")


def is_logging_enabled() -> bool:
    return os.environ.get("EMAIL_SENDS_LOG", "1").strip().lower() not in ("0", "false", "no", "off")


def is_dedup_enabled() -> bool:
    return os.environ.get("EMAIL_DEDUP", "1").strip().lower() not in ("0", "false", "no", "off")


def dedup_window_days() -> int:
    raw = (os.environ.get("EMAIL_DEDUP_DAYS") or "15").strip()
    try:
        n = int(raw)
    except ValueError:
        return 15
    return max(1, min(n, 366))


def normalize_dedup_email(s: str | None) -> str:
    if not s:
        return ""
    return str(s).strip().lower()


def normalize_dedup_text(s: str | None) -> str:
    """Collapse whitespace and lowercase (matches intent of job company/role strings)."""
    if s is None:
        return ""
    t = str(s).strip()
    if not t or t.lower() == "nan":
        return ""
    return " ".join(t.replace("_", " ").split()).lower()


def has_recent_application(
    recipient_email: str,
    company: str | None,
    role: str | None,
    *,
    days: int | None = None,
    db_path: Path | str | None = None,
) -> bool:
    """
    True if any table has a real send (success=1, dry_run=0) for the same
    normalized email + company + role within the last `days` (default from EMAIL_DEDUP_DAYS).
    """
    em = normalize_dedup_email(recipient_email)
    if not em or "@" not in em:
        return False
    co = normalize_dedup_text(company)
    ro = normalize_dedup_text(role)
    n = days if days is not None else dedup_window_days()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=n)).isoformat()
    p = Path(db_path) if db_path is not None else get_db_path()
    if not p.is_file():
        return False
    try:
        with sqlite3.connect(p, timeout=30) as conn:
            for table in ALLOWED_TABLES:
                cur = conn.execute(
                    f"""
                    SELECT company, role FROM {table}
                    WHERE lower(trim(recipient_email)) = ?
                      AND created_at >= ?
                      AND success = 1 AND dry_run = 0
                    """,
                    (em, cutoff),
                )
                for c, r in cur:
                    if normalize_dedup_text(c) == co and normalize_dedup_text(r) == ro:
                        return True
    except sqlite3.Error as e:
        logger.warning("email_sends_db: dedup check failed: %s", e)
    return False


def duplicate_skip_reason() -> str:
    return f"duplicate_same_job_email_within_{dedup_window_days()}_days"


def get_db_path() -> Path:
    raw = (os.environ.get("EMAIL_SENDS_DB") or "data/email_sends.db").strip()
    return Path(raw)


def init_db(path: Path | str | None = None) -> None:
    if not is_logging_enabled():
        return
    p = Path(path) if path is not None else get_db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(p) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        for table in ALLOWED_TABLES:
            conn.execute(f"CREATE TABLE IF NOT EXISTS {table} ({_CREATE_COLUMNS})")
            for col in _INDEX_SUFFIXES:
                idx = f"idx_{table}_{col}"
                conn.execute(f"CREATE INDEX IF NOT EXISTS {idx} ON {table}({col})")
        conn.commit()


def log_email_send(
    table_name: str,
    *,
    recipient_email: str,
    success: bool,
    dry_run: bool = False,
    company: str | None = None,
    role: str | None = None,
    region: str | None = None,
    subject: str | None = None,
    pdf_path: str | None = None,
    pdf_filename: str | None = None,
    excel_path: str | None = None,
    failure_reason: str | None = None,
    db_path: Path | str | None = None,
) -> None:
    if not is_logging_enabled():
        return
    if table_name not in ALLOWED_TABLES:
        logger.warning("email_sends_db: unknown table %r, skip log", table_name)
        return
    created_at = datetime.now(timezone.utc).isoformat()
    p = Path(db_path) if db_path is not None else get_db_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(p, timeout=30) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(
                f"""
                INSERT INTO {table_name} (
                    created_at, recipient_email, success, dry_run,
                    company, role, region, subject, pdf_path, pdf_filename,
                    excel_path, failure_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    recipient_email or "",
                    1 if success else 0,
                    1 if dry_run else 0,
                    company,
                    role,
                    region,
                    subject,
                    pdf_path,
                    pdf_filename,
                    excel_path,
                    failure_reason,
                ),
            )
            conn.commit()
    except sqlite3.Error as e:
        logger.warning("email_sends_db: failed to log send: %s", e)
