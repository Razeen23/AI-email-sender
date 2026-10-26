from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.models.schemas import SendJobRequest
from backend.services.job_runner import JobBusyError, runner

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/current")
def current_job() -> dict:
    return {"job": runner.snapshot()}


@router.post("/send")
def start_send(payload: SendJobRequest) -> dict:
    try:
        job = runner.start(
            excel_path=payload.excel_path,
            region=payload.region,
            dry_run=payload.dry_run,
            row_indexes=payload.row_indexes,
            resume_overrides=payload.resume_overrides,
        )
    except JobBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return job


@router.get("/{job_id}")
def get_job(job_id: str) -> dict:
    job = runner.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@router.post("/{job_id}/cancel")
def cancel_job(job_id: str) -> dict:
    try:
        return runner.cancel(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{job_id}/stream")
async def stream_job(job_id: str) -> StreamingResponse:
    if not runner.get(job_id):
        raise HTTPException(status_code=404, detail="Job not found.")

    async def generate():
        cursor = 0
        terminal = {"completed", "cancelled", "failed"}
        while True:
            job = runner.get(job_id)
            if not job:
                yield f"data: {json.dumps({'type': 'error', 'reason': 'job_missing'})}\n\n"
                break
            events = job["events"][cursor:]
            for event in events:
                cursor += 1
                yield f"data: {json.dumps(event)}\n\n"
            if job["status"] in terminal and cursor >= len(job["events"]):
                last_type = job["events"][-1]["type"] if job["events"] else None
                if last_type not in {"done", "cancelled", "error"}:
                    payload = {"type": "done", "status": job["status"], **{k: job[k] for k in ("sent", "failed", "skipped", "processed", "total")}}
                    yield f"data: {json.dumps(payload)}\n\n"
                break
            await asyncio.sleep(0.4)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
