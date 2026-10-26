from __future__ import annotations

import logging
import threading
import time

from backend.clock import new_id
from backend.models.schemas import SendIn
from backend.paths import daily_cap, send_delay_seconds
from backend.repositories import jobs_repo, sends_repo
from backend.services import country_service, email_service, mailbox_service, profile_service, resume_service
from backend.textutil import clean_header, clip

logger = logging.getLogger(__name__)


class JobBusyError(RuntimeError):
    pass


def _outcome(job_id: str, company: str, status: str, error: str, attempted: bool) -> dict:
    return {
        "job_id": job_id,
        "company": company,
        "status": status,
        "error": error,
        "attempted_smtp": attempted,
    }


def _record(
    user_id: str,
    job: dict,
    *,
    country_label: str,
    status: str,
    subject: str,
    body: str,
    resume_filename: str,
    error: str,
) -> None:
    sends_repo.record(
        user_id,
        job_id=job["id"],
        company=job["company"],
        role=job["role"],
        contact_email=job["contact_email"],
        country_label=country_label,
        status=status,
        subject=subject,
        body=body,
        resume_filename=resume_filename,
        error=error,
    )


def process_item(user_id: str, item: dict, *, dry_run: bool, mailer=None) -> dict:
    sender = mailer or email_service.send_message
    job_id = item.get("job_id", "")
    job = jobs_repo.get(user_id, job_id)
    if not job:
        return _outcome(job_id, "", "failed", "That job is no longer on your list.", False)
    subject = clean_header(clip(str(item.get("subject", "")), 150))
    body = clip(str(item.get("body", "")).strip(), 8000)
    if not subject or not body:
        _record(
            user_id,
            job,
            country_label="",
            status="failed",
            subject=subject,
            body=body,
            resume_filename="",
            error="Preview the job before sending.",
        )
        return _outcome(job_id, job["company"], "failed", "Preview the job before sending.", False)
    attempted = False
    country_label = ""
    filename = ""
    try:
        chosen = job["country_id"] or str(item.get("country_id") or "")
        if not chosen:
            raise ValueError("Choose a target country for this job.")
        country = country_service.require(user_id, chosen)
        country_label = country["label"]
        if sends_repo.already_sent(user_id, job["company"], job["role"], job["contact_email"]):
            error = "Already sent to this company, role, and address."
            _record(
                user_id,
                job,
                country_label=country_label,
                status="skipped_dedup",
                subject=subject,
                body=body,
                resume_filename="",
                error=error,
            )
            return _outcome(job_id, job["company"], "skipped_dedup", error, False)
        if not dry_run and sends_repo.count_sent_today(user_id) >= daily_cap():
            error = f"Daily cap of {daily_cap()} sent applications reached."
            _record(
                user_id,
                job,
                country_label=country_label,
                status="failed",
                subject=subject,
                body=body,
                resume_filename="",
                error=error,
            )
            return _outcome(job_id, job["company"], "failed", error, False)
        profile = profile_service.get_profile(user_id)
        mode = item.get("resume_mode") or "own"
        file_attachment = resume_service.attachment(
            user_id,
            profile,
            country,
            job,
            mode,
            resume_id=str(item.get("resume_id") or ""),
        )
        if not file_attachment:
            error = "No resume is available for this email."
            _record(
                user_id,
                job,
                country_label=country_label,
                status="failed",
                subject=subject,
                body=body,
                resume_filename="",
                error=error,
            )
            return _outcome(job_id, job["company"], "failed", error, False)
        filename = file_attachment[0]
        if dry_run:
            _record(
                user_id,
                job,
                country_label=country_label,
                status="dry_run",
                subject=subject,
                body=body,
                resume_filename=filename,
                error="",
            )
            return _outcome(job_id, job["company"], "dry_run", "", False)
        mailbox = mailbox_service.credentials(user_id)
        attempted = True
        sender(
            host=mailbox["host"],
            port=mailbox["port"],
            username=mailbox["username"],
            password=mailbox["password"],
            from_name=mailbox["from_name"],
            from_email=mailbox["from_email"],
            to_email=job["contact_email"],
            subject=subject,
            body=body,
            attachment=file_attachment,
        )
        _record(
            user_id,
            job,
            country_label=country_label,
            status="sent",
            subject=subject,
            body=body,
            resume_filename=filename,
            error="",
        )
        return _outcome(job_id, job["company"], "sent", "", True)
    except Exception as exc:
        error = str(exc).strip() or "Send failed."
        logger.info("Application was not sent for user %s: %s", user_id, error)
        _record(
            user_id,
            job,
            country_label=country_label,
            status="failed",
            subject=subject,
            body=body,
            resume_filename=filename,
            error=error,
        )
        return _outcome(job_id, job["company"], "failed", error, attempted)


class SendRunner:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runs: dict[str, dict] = {}
        self._active: set[str] = set()

    def start(self, user_id: str, body: SendIn) -> dict:
        if not body.items:
            raise ValueError("Select at least one job.")
        if len(body.items) > daily_cap():
            raise ValueError(f"Send up to {daily_cap()} jobs at a time.")
        if not body.dry_run:
            mailbox_service.require_ready(user_id)
        for item in body.items:
            if not item.subject.strip() or not item.body.strip():
                raise ValueError("Each application needs a subject and a body. Preview the jobs first.")
        run_id = new_id()
        run = {
            "id": run_id,
            "user_id": user_id,
            "status": "running",
            "dry_run": body.dry_run,
            "total": len(body.items),
            "processed": 0,
            "sent": 0,
            "failed": 0,
            "skipped": 0,
            "dry_runs": 0,
            "results": [],
            "error": "",
        }
        with self._lock:
            if user_id in self._active:
                raise JobBusyError("A send is already running for your account.")
            self._runs[run_id] = run
            self._active.add(user_id)
        items = [item.model_dump() for item in body.items]
        thread = threading.Thread(
            target=self._execute,
            args=(user_id, run_id, body.dry_run, items),
            daemon=False,
            name=f"send-{run_id[:8]}",
        )
        try:
            thread.start()
        except Exception:
            self._finish(run_id, user_id)
            with self._lock:
                self._runs[run_id]["error"] = "Could not start the send."
            raise
        return self.get(user_id, run_id)

    def get(self, user_id: str, run_id: str) -> dict:
        with self._lock:
            run = self._runs.get(run_id)
            if not run or run["user_id"] != user_id:
                raise LookupError("Send run not found.")
            return {
                "id": run["id"],
                "status": run["status"],
                "dry_run": run["dry_run"],
                "total": run["total"],
                "processed": run["processed"],
                "sent": run["sent"],
                "failed": run["failed"],
                "skipped": run["skipped"],
                "dry_runs": run["dry_runs"],
                "results": [dict(item) for item in run["results"]],
                "error": run["error"],
            }

    def _add(self, run_id: str, result: dict) -> None:
        with self._lock:
            run = self._runs[run_id]
            run["processed"] += 1
            status = result["status"]
            if status == "sent":
                run["sent"] += 1
            elif status == "failed":
                run["failed"] += 1
            elif status == "skipped_dedup":
                run["skipped"] += 1
            elif status == "dry_run":
                run["dry_runs"] += 1
            run["results"].append(
                {
                    "job_id": result["job_id"],
                    "company": result["company"],
                    "status": status,
                    "error": result["error"],
                }
            )

    def _finish(self, run_id: str, user_id: str) -> None:
        with self._lock:
            run = self._runs.get(run_id)
            if run:
                run["status"] = "done"
            self._active.discard(user_id)

    def _execute(self, user_id: str, run_id: str, dry_run: bool, items: list[dict]) -> None:
        delay = send_delay_seconds()
        previous_attempt = False
        try:
            for item in items:
                if previous_attempt and not dry_run and delay:
                    time.sleep(delay)
                result = process_item(user_id, item, dry_run=dry_run)
                previous_attempt = bool(result["attempted_smtp"])
                self._add(run_id, result)
        except Exception:
            logger.exception("Send run failed")
            with self._lock:
                if run_id in self._runs:
                    self._runs[run_id]["error"] = "The send stopped unexpectedly."
        finally:
            self._finish(run_id, user_id)


runner = SendRunner()
