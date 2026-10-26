from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone

from backend.paths import resolve_excel_path
from backend.services.config_service import smtp_configured
from backend.services.send_service import run_send_job

ACTIVE_STATUSES = {"queued", "running", "cancelling"}


class JobBusyError(RuntimeError):
    pass


class JobRunner:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._job: dict | None = None

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def snapshot(self) -> dict | None:
        with self._lock:
            if not self._job:
                return None
            return self._public(self._job)

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            if not self._job or self._job["id"] != job_id:
                return None
            return self._public(self._job)

    def events_from(self, job_id: str, start: int = 0) -> list[dict]:
        with self._lock:
            if not self._job or self._job["id"] != job_id:
                return []
            return list(self._job["events"][start:])

    def start(
        self,
        *,
        excel_path: str,
        region: str,
        dry_run: bool,
        row_indexes: list[int],
        resume_overrides: dict[int, str],
    ) -> dict:
        if not row_indexes:
            raise ValueError("Select at least one row to send.")
        if not dry_run and not smtp_configured():
            raise ValueError("SMTP is not configured. Add credentials to .env or use dry-run.")
        resolve_excel_path(excel_path)
        with self._lock:
            if self._job and self._job["status"] in ACTIVE_STATUSES:
                raise JobBusyError("A send job is already running.")
            job_id = uuid.uuid4().hex[:12]
            cancel_event = threading.Event()
            self._job = {
                "id": job_id,
                "status": "queued",
                "dry_run": dry_run,
                "excel_path": excel_path,
                "region": region,
                "total": len(row_indexes),
                "processed": 0,
                "sent": 0,
                "failed": 0,
                "skipped": 0,
                "events": [],
                "error": None,
                "started_at": self._now(),
                "finished_at": None,
                "cancel_event": cancel_event,
            }
            thread = threading.Thread(
                target=self._run,
                kwargs={
                    "job_id": job_id,
                    "excel_path": excel_path,
                    "region": region,
                    "dry_run": dry_run,
                    "row_indexes": row_indexes,
                    "resume_overrides": resume_overrides,
                },
                daemon=True,
            )
            thread.start()
            return self._public(self._job)

    def cancel(self, job_id: str) -> dict:
        with self._lock:
            if not self._job or self._job["id"] != job_id:
                raise FileNotFoundError("Job not found.")
            if self._job["status"] not in ACTIVE_STATUSES:
                return self._public(self._job)
            self._job["status"] = "cancelling"
            self._job["cancel_event"].set()
            return self._public(self._job)

    def _append(self, event: dict) -> None:
        with self._lock:
            if not self._job:
                return
            self._job["events"].append(event)
            for key in ("processed", "sent", "failed", "skipped", "total"):
                if key in event:
                    self._job[key] = event[key]
            if event.get("type") in {"started", "generating", "sending"}:
                self._job["status"] = "running"

    def _run(
        self,
        *,
        job_id: str,
        excel_path: str,
        region: str,
        dry_run: bool,
        row_indexes: list[int],
        resume_overrides: dict[int, str],
    ) -> None:
        cancel_event = None
        with self._lock:
            if self._job and self._job["id"] == job_id:
                self._job["status"] = "running"
                cancel_event = self._job["cancel_event"]
        try:
            result = run_send_job(
                excel_path=excel_path,
                region=region,
                dry_run=dry_run,
                row_indexes=row_indexes,
                resume_overrides=resume_overrides,
                cancel_event=cancel_event,
                progress=self._append,
            )
            with self._lock:
                if self._job and self._job["id"] == job_id:
                    self._job["status"] = result.get("status") or "completed"
                    self._job["processed"] = result.get("processed", self._job["processed"])
                    self._job["sent"] = result.get("sent", self._job["sent"])
                    self._job["failed"] = result.get("failed", self._job["failed"])
                    self._job["skipped"] = result.get("skipped", self._job["skipped"])
                    self._job["finished_at"] = self._now()
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                if self._job and self._job["id"] == job_id:
                    self._job["status"] = "failed"
                    self._job["error"] = str(exc)
                    self._job["finished_at"] = self._now()
                    self._job["events"].append({"type": "error", "reason": str(exc)})

    def _public(self, job: dict) -> dict:
        return {
            "id": job["id"],
            "status": job["status"],
            "dry_run": job["dry_run"],
            "excel_path": job["excel_path"],
            "region": job["region"],
            "total": job["total"],
            "processed": job["processed"],
            "sent": job["sent"],
            "failed": job["failed"],
            "skipped": job["skipped"],
            "events": list(job["events"]),
            "error": job["error"],
            "started_at": job["started_at"],
            "finished_at": job["finished_at"],
        }


runner = JobRunner()
