from app.models.config import ConfigSnapshot, SourceConfig
from app.tasks import scheduler as scheduler_module
from app.tasks.scheduler import build_scheduler, reload_scheduler, stop_scheduler


def test_scheduler_registers_jobs_for_enabled_sources() -> None:
    scheduler = build_scheduler()
    jobs = scheduler.get_jobs()

    assert any(job.id == "sync:douban_group_656297_tab_42899" for job in jobs)
    assert any(job.id == "sync:smzdm_keywords_primary" for job in jobs)


def test_reload_scheduler_rebuilds_jobs(monkeypatch) -> None:
    stop_scheduler()

    initial = ConfigSnapshot(
        source_files=[],
        rule_files=[],
        sources=[SourceConfig(source_key="source_a", enabled=True, interval_minutes=5)],
        rules=[],
    )
    updated = ConfigSnapshot(
        source_files=[],
        rule_files=[],
        sources=[SourceConfig(source_key="source_b", enabled=True, interval_minutes=15)],
        rules=[],
    )
    snapshots = iter([initial, updated])
    monkeypatch.setattr(scheduler_module, "load_config_snapshot", lambda: next(snapshots))

    scheduler = build_scheduler()
    assert [job.id for job in scheduler.get_jobs()] == ["sync:source_a"]
    scheduler_module._scheduler = scheduler

    reloaded = reload_scheduler()
    assert [job.id for job in reloaded.get_jobs()] == ["sync:source_b"]
    stop_scheduler()
