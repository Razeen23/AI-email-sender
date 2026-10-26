from __future__ import annotations

from backend.repositories import sends_repo


def stats(user_id: str) -> dict:
    counts = sends_repo.status_counts(user_id)
    sent = counts.get("sent", 0)
    failed = counts.get("failed", 0)
    dry_runs = counts.get("dry_run", 0)
    skipped = counts.get("skipped_dedup", 0)
    return {
        "today_sent": sends_repo.count_sent_today(user_id),
        "sent": sent,
        "failed": failed,
        "dry_runs": dry_runs,
        "skipped_dedup": skipped,
        "total_attempts": sent + failed + dry_runs + skipped,
        "by_country": sends_repo.sent_by_country(user_id),
        "recent": sends_repo.list_for_user(user_id, limit=8),
    }


def history(user_id: str) -> list[dict]:
    return sends_repo.list_for_user(user_id, limit=200)
