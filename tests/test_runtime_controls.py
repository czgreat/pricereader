from app.services.ingestion import sync_and_evaluate_new_items
from app.services.storage import SourceItemRepository


def test_sync_skips_paused_source(monkeypatch, tmp_path) -> None:
    from app.services import ingestion as ingestion_module

    repo = SourceItemRepository(db_path=tmp_path / "controls.db")
    repo.set_source_paused(source_key="smzdm_keywords_primary", paused=True, reason="manual pause")
    monkeypatch.setattr(ingestion_module, "SourceItemRepository", lambda: repo)

    result = sync_and_evaluate_new_items("smzdm_keywords_primary", 3)

    assert result.inserted == 0
    assert result.skipped_reason == "source_paused: manual pause"


def test_source_controls_and_mutes_are_persisted(tmp_path) -> None:
    repo = SourceItemRepository(db_path=tmp_path / "controls-2.db")
    pause = repo.set_source_paused(source_key="douban_group_656297_tab_42899", paused=True, reason="maintenance")
    mute = repo.set_item_muted(source_key="douban_group_656297_tab_42899", external_id="topic-1", muted=True, reason="noise")

    controls = repo.list_source_controls(limit=10)
    mutes = repo.list_item_mutes(limit=10)

    assert pause.paused is True
    assert mute.muted is True
    assert controls[0].source_key == "douban_group_656297_tab_42899"
    assert mutes[0].external_id == "topic-1"
