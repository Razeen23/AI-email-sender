from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path
from threading import Event

from backend.paths import resolve_excel_path, resolve_resume_path, to_rel
from backend.services.config_service import get_send_config, smtp_configured
from backend.services.excel_service import load_send_rows
from email_sends_db import (
    TABLE_SEND_EMAILS2,
    duplicate_skip_reason,
    has_recent_application,
    init_db,
    is_dedup_enabled,
    is_logging_enabled,
    log_email_send,
)
from resume_selection import get_resume_path
from send_emails2 import (
    DELAY_SECONDS,
    build_and_send,
    generate_body,
    get_signature_block,
    get_subject,
    load_profile,
    strip_leading_subject_line,
    strip_trailing_contact_block,
    strip_trailing_sign_off,
)

logger = logging.getLogger("backend.send")
ProgressFn = Callable[[dict], None]


def _emit(progress: ProgressFn | None, payload: dict) -> None:
    if progress:
        progress(payload)


def _clean_body(body: str, region: str) -> str:
    cleaned = strip_leading_subject_line(
        strip_trailing_sign_off(strip_trailing_contact_block(strip_trailing_sign_off(body)))
    )
    return cleaned + "\n\n" + get_signature_block(region)


def _wait_or_cancel(cancel_event: Event | None, seconds: int, progress: ProgressFn | None) -> bool:
    remaining = seconds
    while remaining > 0:
        if cancel_event and cancel_event.is_set():
            return True
        _emit(progress, {"type": "waiting", "seconds_left": remaining})
        step = 1 if remaining >= 1 else remaining
        time.sleep(step)
        remaining -= step
    return bool(cancel_event and cancel_event.is_set())


def run_send_job(
    *,
    excel_path: str,
    region: str,
    dry_run: bool,
    row_indexes: list[int],
    resume_overrides: dict[int, str] | None = None,
    cancel_event: Event | None = None,
    progress: ProgressFn | None = None,
) -> dict:
    if not dry_run and not smtp_configured():
        raise ValueError("SMTP is not configured. Add credentials to .env or use dry-run.")
    if not row_indexes:
        raise ValueError("Select at least one row to send.")

    resolve_excel_path(excel_path)
    resolved_region, all_rows = load_send_rows(excel_path, region)
    by_index = {row["index"]: row for row in all_rows}
    selected: list[dict] = []
    for index in row_indexes:
        row = by_index.get(index)
        if row is None:
            raise ValueError(f"Row {index} is not in this Excel file.")
        selected.append(row)

    overrides = resume_overrides or {}
    config = get_send_config()
    if is_logging_enabled():
        init_db()
    profile_text = load_profile(config, logger)
    ollama_state: dict = {}

    counts = {"sent": 0, "failed": 0, "skipped": 0, "processed": 0}
    total = len(selected)
    _emit(
        progress,
        {
            "type": "started",
            "total": total,
            "dry_run": dry_run,
            "region": resolved_region,
            "excel_path": excel_path,
        },
    )

    for position, row in enumerate(selected):
        if cancel_event and cancel_event.is_set():
            _emit(progress, {"type": "cancelled", **counts, "total": total})
            return {**counts, "total": total, "status": "cancelled"}

        company = row["company"]
        role = row["role"]
        to_email = row["email"]
        job_description = row.get("job_description")
        key_skills = row.get("key_skills")
        why_match = row.get("why_match")
        base_event = {
            "index": row["index"],
            "position": position + 1,
            "total": total,
            "company": company,
            "role": role,
            "email": to_email,
        }

        if not row.get("valid_email"):
            counts["skipped"] += 1
            counts["processed"] += 1
            _emit(progress, {**base_event, "type": "skipped", "reason": "invalid_email", **counts})
            continue

        resume_abs: str | None = None
        override = overrides.get(row["index"])
        if override:
            resume_abs = str(resolve_resume_path(override))
        else:
            resume_abs = get_resume_path(
                config["resumes_base"],
                resolved_region,
                role,
                logger,
                job_description=job_description,
                key_skills=key_skills,
                why_match=why_match,
            )

        if not resume_abs:
            counts["failed"] += 1
            counts["processed"] += 1
            log_email_send(
                TABLE_SEND_EMAILS2,
                recipient_email=to_email,
                success=False,
                dry_run=dry_run,
                company=company or None,
                role=role or None,
                region=resolved_region,
                subject=get_subject(company, role),
                excel_path=excel_path,
                failure_reason="no_resume",
            )
            _emit(progress, {**base_event, "type": "failed", "reason": "no_resume", **counts})
            continue

        resume_file = Path(resume_abs)
        pdf_rel = to_rel(resume_file)

        if is_dedup_enabled() and has_recent_application(to_email, company or None, role or None):
            reason = duplicate_skip_reason()
            counts["skipped"] += 1
            counts["processed"] += 1
            log_email_send(
                TABLE_SEND_EMAILS2,
                recipient_email=to_email,
                success=False,
                dry_run=dry_run,
                company=company or None,
                role=role or None,
                region=resolved_region,
                subject=get_subject(company, role),
                pdf_path=str(resume_file.resolve()),
                pdf_filename=resume_file.name,
                excel_path=excel_path,
                failure_reason=reason,
            )
            _emit(progress, {**base_event, "type": "skipped", "reason": reason, "resume_path": pdf_rel, **counts})
            continue

        _emit(progress, {**base_event, "type": "generating", "resume_path": pdf_rel})
        body = generate_body(
            company,
            role,
            job_description,
            key_skills,
            why_match,
            profile_text,
            config,
            logger,
            ollama_state=ollama_state,
        )
        if not body:
            counts["failed"] += 1
            counts["processed"] += 1
            log_email_send(
                TABLE_SEND_EMAILS2,
                recipient_email=to_email,
                success=False,
                dry_run=dry_run,
                company=company or None,
                role=role or None,
                region=resolved_region,
                subject=get_subject(company, role),
                pdf_path=str(resume_file.resolve()),
                pdf_filename=resume_file.name,
                excel_path=excel_path,
                failure_reason="no_body",
            )
            _emit(progress, {**base_event, "type": "failed", "reason": "no_body", "resume_path": pdf_rel, **counts})
            continue

        body = _clean_body(body, resolved_region)
        _emit(progress, {**base_event, "type": "sending", "resume_path": pdf_rel, "dry_run": dry_run})
        ok, err = build_and_send(to_email, company, role, body, resume_abs, config, dry_run, logger)
        log_email_send(
            TABLE_SEND_EMAILS2,
            recipient_email=to_email,
            success=ok,
            dry_run=dry_run,
            company=company or None,
            role=role or None,
            region=resolved_region,
            subject=get_subject(company, role),
            pdf_path=str(resume_file.resolve()),
            pdf_filename=resume_file.name,
            excel_path=excel_path,
            failure_reason=err,
        )
        counts["processed"] += 1
        if ok:
            counts["sent"] += 1
            _emit(progress, {**base_event, "type": "sent", "resume_path": pdf_rel, "dry_run": dry_run, **counts})
        else:
            counts["failed"] += 1
            _emit(progress, {**base_event, "type": "failed", "reason": err or "smtp_error", "resume_path": pdf_rel, **counts})
            continue

        if not dry_run and position < total - 1:
            if _wait_or_cancel(cancel_event, DELAY_SECONDS, progress):
                _emit(progress, {"type": "cancelled", **counts, "total": total})
                return {**counts, "total": total, "status": "cancelled"}

    status = "completed"
    _emit(progress, {"type": "done", **counts, "total": total, "status": status})
    return {**counts, "total": total, "status": status}
