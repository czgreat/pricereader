from __future__ import annotations

import logging
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.services.config_loader import load_config_snapshot
from app.services.ingestion import sync_and_evaluate_new_items
from app.services.storage import SourceItemRepository

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _job_sync_source(source_key: str, max_items: int) -> None:
    result = sync_and_evaluate_new_items(source_key, max_items=max_items)
    logger.info(
        "Scheduled sync finished for %s: inserted=%s updated=%s evaluated_new=%s reevaluated=%s notifications=%s/%s skipped=%s",
        result.source_key,
        result.inserted,
        result.updated,
        result.evaluated_new_items,
        result.reevaluated_existing_items,
        result.notifications_sent,
        result.notifications_attempted,
        result.notifications_skipped,
    )


def build_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    snapshot = load_config_snapshot()
    for source in snapshot.sources:
        if not source.enabled or not source.interval_minutes:
            continue
        max_items = source.max_items or (5 if "smzdm" in source.source_key else 3)
        scheduler.add_job(
            _job_sync_source,
            trigger=IntervalTrigger(minutes=source.interval_minutes),
            id=f"sync:{source.source_key}",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            kwargs={"source_key": source.source_key, "max_items": max_items},
        )
    return scheduler


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = build_scheduler()
    if not _scheduler.running:
        _scheduler.start()
    return _scheduler


def reload_scheduler() -> BackgroundScheduler:
    global _scheduler
    should_start = _scheduler is None or _scheduler.running
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = build_scheduler()
    if should_start:
        _scheduler.start()
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None


def scheduler_status() -> dict[str, Any]:
    snapshot = load_config_snapshot()
    repository = SourceItemRepository()
    controls = {item.source_key: item for item in repository.list_source_controls(limit=200)}
    health = {item.source_key: item for item in repository.list_source_health(limit=200)}
    jobs = []
    if _scheduler:
        jobs = [
            {
                "id": job.id,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            }
            for job in _scheduler.get_jobs()
        ]
    return {
        "running": bool(_scheduler and _scheduler.running),
        "configured_sources": [
            {
                "source_key": source.source_key,
                "enabled": source.enabled,
                "interval_minutes": source.interval_minutes,
                "paused": controls.get(source.source_key).paused if controls.get(source.source_key) else False,
                "pause_reason": controls.get(source.source_key).reason if controls.get(source.source_key) else None,
                "status": health.get(source.source_key).status if health.get(source.source_key) else None,
                "backoff_until": health.get(source.source_key).backoff_until if health.get(source.source_key) else None,
            }
            for source in snapshot.sources
        ],
        "jobs": jobs,
    }
