from fastapi import APIRouter, Query

from backend.repositories.sends_repo import SendsRepository

router = APIRouter(tags=["stats"])
repo = SendsRepository()


@router.get("/stats")
def stats() -> dict:
    data = repo.stats()
    data["recent"] = repo.recent(8)
    return data


@router.get("/sends")
def sends(
    q: str | None = None,
    success: int | None = Query(default=None, ge=0, le=1),
    region: str | None = None,
    dry_run: int | None = Query(default=None, ge=0, le=1),
    source: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    return repo.list_sends(
        q=q,
        success=success,
        region=region,
        dry_run=dry_run,
        source=source,
        limit=limit,
        offset=offset,
    )
