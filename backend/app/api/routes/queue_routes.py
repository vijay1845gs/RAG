"""
Queue observability routes — Phase 7.

Provides real-time queue stats for the Dashboard's "Queue Intelligence" widget:
  - Active / queued / failed job counts
  - Redis connection status
  - Cache hit rate
  - Average processing time (from Supabase)
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/queue", tags=["Queue"])


@router.get("/stats", response_model=dict)
async def get_queue_stats(
    user_id: Optional[str] = Query(None, description="Filter stats by user"),
):
    """
    Return queue and cache statistics for the Dashboard.

    Data sources:
      - Supabase documents table: job counts by processing_status
      - Redis: cache hit/miss stats, connection status
      - Celery inspect: active/reserved task counts (best-effort)
    """
    stats = {
        "queued_jobs":         0,
        "active_jobs":         0,
        "completed_jobs":      0,
        "failed_jobs":         0,
        "retrying_jobs":       0,
        "avg_processing_time": None,
        "completion_rate":     None,
        "cache": {
            "connected":      False,
            "hit_rate":       0.0,
            "used_memory":    "—",
        },
        "worker": {
            "online":         False,
            "active_tasks":   0,
        },
    }

    # ── 1. Count jobs from Supabase by processing_status ─────────────────────
    try:
        from app.db.supabase import get_supabase_admin_client
        sb = get_supabase_admin_client()
        if sb:
            query = sb.table("documents").select("processing_status, processing_started_at, processing_completed_at")
            if user_id:
                query = query.eq("user_id", user_id)
            res = query.execute()

            rows = res.data or []
            processing_times = []

            for row in rows:
                s = row.get("processing_status", "")
                if s == "queued":
                    stats["queued_jobs"] += 1
                elif s == "processing":
                    stats["active_jobs"] += 1
                elif s == "completed":
                    stats["completed_jobs"] += 1
                    # Compute processing time
                    started = row.get("processing_started_at")
                    completed = row.get("processing_completed_at")
                    if started and completed:
                        try:
                            from datetime import datetime
                            s_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                            c_dt = datetime.fromisoformat(completed.replace("Z", "+00:00"))
                            processing_times.append((c_dt - s_dt).total_seconds())
                        except Exception:
                            pass
                elif s == "failed":
                    stats["failed_jobs"] += 1
                elif s == "retrying":
                    stats["retrying_jobs"] += 1

            # Average processing time
            if processing_times:
                stats["avg_processing_time"] = round(sum(processing_times) / len(processing_times), 1)

            # Completion rate
            total = len(rows)
            if total > 0:
                stats["completion_rate"] = round(stats["completed_jobs"] / total * 100, 1)

    except Exception as exc:
        logger.warning("Failed to fetch queue stats from Supabase: %s", exc)

    # ── 2. Redis cache stats ──────────────────────────────────────────────────
    try:
        from app.services.cache_service import chat_cache
        cache_stats = chat_cache.get_stats()
        stats["cache"] = {
            "connected":   cache_stats.get("connected", False),
            "hit_rate":    cache_stats.get("cache_hit_rate", 0.0),
            "used_memory": cache_stats.get("used_memory_human", "—"),
        }
    except Exception as exc:
        logger.warning("Failed to fetch Redis stats: %s", exc)

    # ── 3. Celery worker inspect (best-effort, non-blocking) ──────────────────
    try:
        from app.core.celery_app import celery_app
        inspector = celery_app.control.inspect(timeout=1.0)
        active = inspector.active() or {}
        reserved = inspector.reserved() or {}

        active_count = sum(len(v) for v in active.values())
        reserved_count = sum(len(v) for v in reserved.values())

        stats["worker"] = {
            "online":       len(active) > 0,
            "active_tasks": active_count,
            "queued_tasks": reserved_count,
        }
    except Exception as exc:
        logger.debug("Celery inspect unavailable (non-critical): %s", exc)

    return stats


__all__ = ["router"]
