from app.models.config import ConfigSnapshot, SourceConfig
from app.services.ingestion import sync_and_evaluate_new_items
from app.services.ingestion import sync_all_enabled_sources
from app.services.storage import SourceItemRepository


def test_sync_and_evaluate_new_items_creates_evaluations(monkeypatch, tmp_path) -> None:
    from app.models.source_items import SourceFetchResponse, SourceItem
    from app.services import ingestion as ingestion_module

    def fake_fetch(_: str, max_items: int):
        return SourceFetchResponse(
            source_key="smzdm_keywords_primary",
            source_label="什么值得买 / 官方RSS",
            requested_items=max_items,
            returned_items=1,
            items=[
                SourceItem(
                    source_key="smzdm_keywords_primary",
                    external_id="smzdm-demo-1",
                    title="欧乐B iO3 电动牙刷 到手339元",
                    url="https://www.smzdm.com/p/demo-1/",
                    source_type="smzdm_feed",
                    summary="整机好价，适合自用。",
                )
            ],
        )

    repo = SourceItemRepository(db_path=tmp_path / "eval.db")
    monkeypatch.setattr(ingestion_module, "_fetch_source_sample", fake_fetch)
    monkeypatch.setattr(ingestion_module, "SourceItemRepository", lambda: repo)

    result = sync_and_evaluate_new_items("smzdm_keywords_primary", 1)
    records = repo.list_evaluation_records(limit=10)

    assert result.inserted == 1
    assert result.evaluated_new_items == 1
    assert result.evaluation_records_written >= 1
    assert any(record.rule_key == "oralb_io3" for record in records)


def test_sync_reevaluates_materially_changed_existing_items(monkeypatch, tmp_path) -> None:
    from app.models.source_items import SourceFetchResponse, SourceItem
    from app.services import ingestion as ingestion_module

    initial = SourceItem(
        source_key="smzdm_keywords_primary",
        external_id="smzdm-demo-2",
        title="欧乐B iO3 电动牙刷 到手339元",
        url="https://www.smzdm.com/p/demo-2/",
        source_type="smzdm_feed",
        summary="整机好价，适合自用。",
        reply_count=0,
        last_active_text="",
    )
    changed = initial.model_copy(update={"reply_count": 8, "last_active_text": "03-29 09:00"})

    calls = {"count": 0}

    def fake_fetch(_: str, max_items: int):
        calls["count"] += 1
        item = initial if calls["count"] == 1 else changed
        return SourceFetchResponse(
            source_key="smzdm_keywords_primary",
            source_label="什么值得买 / 官方RSS",
            requested_items=max_items,
            returned_items=1,
            items=[item],
        )

    repo = SourceItemRepository(db_path=tmp_path / "eval-recheck.db")
    monkeypatch.setattr(ingestion_module, "_fetch_source_sample", fake_fetch)
    monkeypatch.setattr(ingestion_module, "SourceItemRepository", lambda: repo)

    first = sync_and_evaluate_new_items("smzdm_keywords_primary", 1)
    second = sync_and_evaluate_new_items("smzdm_keywords_primary", 1)

    assert first.inserted == 1
    assert second.updated == 1
    assert second.reevaluated_existing_items == 1
    assert second.evaluated_new_items == 0


def test_sync_all_enabled_sources_isolates_failures(monkeypatch) -> None:
    from app.services import ingestion as ingestion_module

    snapshot = ConfigSnapshot(
        source_files=[],
        rule_files=[],
        sources=[
            SourceConfig(source_key="source_a", enabled=True, interval_minutes=5),
            SourceConfig(source_key="source_b", enabled=True, interval_minutes=5),
        ],
        rules=[],
    )

    def fake_sync(source_key: str, max_items: int):
        if source_key == "source_a":
            raise RuntimeError("boom")
        from app.models.evaluation import EvaluationSyncResponse

        return EvaluationSyncResponse(
            source_key=source_key,
            requested_items=max_items,
            fetched_items=1,
            inserted=1,
            updated=0,
            evaluated_new_items=1,
            reevaluated_existing_items=0,
            evaluation_records_written=1,
            notifications_attempted=0,
            notifications_sent=0,
            notifications_skipped=0,
            item_ids=["ok-1"],
        )

    monkeypatch.setattr(ingestion_module, "load_config_snapshot", lambda: snapshot)
    monkeypatch.setattr(ingestion_module, "sync_and_evaluate_new_items", fake_sync)

    results = sync_all_enabled_sources(max_items=3)

    assert len(results) == 2
    assert results[0].source_key == "source_a"
    assert results[0].skipped_reason == "source_error: boom"
    assert results[1].source_key == "source_b"
    assert results[1].inserted == 1
