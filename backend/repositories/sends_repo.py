from __future__ import annotations

from email_sends_db import count_sends, fetch_stats, list_sends


class SendsRepository:
    def stats(self) -> dict:
        return fetch_stats()

    def list_sends(
        self,
        *,
        q: str | None = None,
        success: int | None = None,
        region: str | None = None,
        dry_run: int | None = None,
        source: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        items = list_sends(
            q=q,
            success=success,
            region=region,
            dry_run=dry_run,
            source=source,
            limit=limit,
            offset=offset,
        )
        total = count_sends(q=q, success=success, region=region, dry_run=dry_run, source=source)
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    def recent(self, limit: int = 8) -> list[dict]:
        return list_sends(limit=limit, offset=0)
