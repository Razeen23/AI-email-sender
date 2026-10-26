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


def _union_select() -> str:
    parts = [
        f"""
        SELECT id, created_at, recipient_email, success, dry_run,
               company, role, region, subject, pdf_path, pdf_filename,
               excel_path, failure_reason, '{table}' AS source
        FROM {table}
        """
        for table in ALLOWED_TABLES
    ]
    return " UNION ALL ".join(parts)


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {k: row[k] for k in row.keys()}


def fetch_stats(*, db_path: Path | str | None = None) -> dict:
    """Aggregate counts across all send tables."""
    empty = {
        "total_attempts": 0,
        "sent": 0,
        "failed": 0,
        "dry_runs": 0,
        "skipped_dedup": 0,
        "today_sent": 0,
        "by_region": {},
        "by_source": {},
    }
    p = Path(db_path) if db_path is not None else get_db_path()
    if not p.is_file():
        return empty
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    union = _union_select()
    try:
        with sqlite3.connect(p, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            totals = conn.execute(
                f"""
                SELECT
                  COUNT(*) AS total_attempts,
                  SUM(CASE WHEN success = 1 AND dry_run = 0 THEN 1 ELSE 0 END) AS sent,
                  SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS failed,
                  SUM(CASE WHEN dry_run = 1 THEN 1 ELSE 0 END) AS dry_runs,
                  SUM(CASE WHEN failure_reason LIKE 'duplicate_same_job_email%' THEN 1 ELSE 0 END) AS skipped_dedup,
                  SUM(CASE WHEN success = 1 AND dry_run = 0 AND created_at >= ? THEN 1 ELSE 0 END) AS today_sent
                FROM ({union})
                """,
                (today_start,),
            ).fetchone()
            regions = conn.execute(
                f"""
                SELECT COALESCE(region, 'UNKNOWN') AS region,
                       SUM(CASE WHEN success = 1 AND dry_run = 0 THEN 1 ELSE 0 END) AS sent
                FROM ({union})
                GROUP BY COALESCE(region, 'UNKNOWN')
                """
            ).fetchall()
            sources = conn.execute(
                f"""
                SELECT source,
                       COUNT(*) AS attempts,
                       SUM(CASE WHEN success = 1 AND dry_run = 0 THEN 1 ELSE 0 END) AS sent
                FROM ({union})
                GROUP BY source
                """
            ).fetchall()
    except sqlite3.Error as e:
        logger.warning("email_sends_db: stats query failed: %s", e)
        return empty
    return {
        "total_attempts": int(totals["total_attempts"] or 0),
        "sent": int(totals["sent"] or 0),
        "failed": int(totals["failed"] or 0),
        "dry_runs": int(totals["dry_runs"] or 0),
        "skipped_dedup": int(totals["skipped_dedup"] or 0),
        "today_sent": int(totals["today_sent"] or 0),
        "by_region": {r["region"]: int(r["sent"] or 0) for r in regions},
        "by_source": {
            r["source"]: {"attempts": int(r["attempts"] or 0), "sent": int(r["sent"] or 0)} for r in sources
        },
    }


def _sends_filters(
    *,
    q: str | None,
    success: int | None,
    region: str | None,
    dry_run: int | None,
    source: str | None,
) -> tuple[str, list]:
    clauses: list[str] = ["1=1"]
    params: list = []
    if q:
        like = f"%{q.strip()}%"
        clauses.append(
            "(recipient_email LIKE ? OR IFNULL(company,'') LIKE ? OR IFNULL(role,'') LIKE ? OR IFNULL(subject,'') LIKE ?)"
        )
        params.extend([like, like, like, like])
    if success is not None:
        clauses.append("success = ?")
        params.append(success)
    if region:
        clauses.append("UPPER(IFNULL(region,'')) = ?")
        params.append(region.strip().upper())
    if dry_run is not None:
        clauses.append("dry_run = ?")
        params.append(dry_run)
    if source:
        if source not in ALLOWED_TABLES:
            raise ValueError(f"Unknown source table: {source}")
        clauses.append("source = ?")
        params.append(source)
    return " AND ".join(clauses), params


def count_sends(
    *,
    q: str | None = None,
    success: int | None = None,
    region: str | None = None,
    dry_run: int | None = None,
    source: str | None = None,
    db_path: Path | str | None = None,
) -> int:
    p = Path(db_path) if db_path is not None else get_db_path()
    if not p.is_file():
        return 0
    where, params = _sends_filters(q=q, success=success, region=region, dry_run=dry_run, source=source)
    union = _union_select()
    try:
        with sqlite3.connect(p, timeout=30) as conn:
            row = conn.execute(f"SELECT COUNT(*) FROM ({union}) WHERE {where}", params).fetchone()
            return int(row[0] if row else 0)
    except sqlite3.Error as e:
        logger.warning("email_sends_db: count query failed: %s", e)
        return 0


def list_sends(
    *,
    q: str | None = None,
    success: int | None = None,
    region: str | None = None,
    dry_run: int | None = None,
    source: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db_path: Path | str | None = None,
) -> list[dict]:
    p = Path(db_path) if db_path is not None else get_db_path()
    if not p.is_file():
        return []
    where, params = _sends_filters(q=q, success=success, region=region, dry_run=dry_run, source=source)
    union = _union_select()
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    try:
        with sqlite3.connect(p, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT * FROM ({union})
                WHERE {where}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()
            return [_row_to_dict(r) for r in rows]
    except sqlite3.Error as e:
        logger.warning("email_sends_db: list query failed: %s", e)
        return []
