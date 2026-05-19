from app.models.source_items import SourceItem, SourceItemDetail
from app.services.storage import SourceItemRepository


def test_storage_upsert_and_dedupe(tmp_path) -> None:
    repository = SourceItemRepository(db_path=tmp_path / "test.db")
    item = SourceItem(
        source_key="douban_group_656297_tab_42899",
        external_id="482306083",
        title="【出闲置】小李子兔肉12罐",
        url="https://www.douban.com/group/topic/482306083/",
        source_type="douban_topic",
        author_name="咔咔",
        reply_count=1,
        last_active_text="03-28 18:56",
    )

    first = repository.upsert_items(item.source_key, "label", [item], requested_items=1)
    second = repository.upsert_items(item.source_key, "label", [item], requested_items=1)
    stored = repository.list_items(source_key=item.source_key, limit=10)

    assert first.inserted == 1
    assert first.updated == 0
    assert first.reevaluated_existing == 0
    assert second.inserted == 0
    assert second.updated == 1
    assert second.reevaluated_existing == 0
    assert len(stored) == 1
    assert stored[0].seen_count == 2


def test_storage_marks_material_change_for_reevaluation(tmp_path) -> None:
    repository = SourceItemRepository(db_path=tmp_path / "test-material.db")
    item = SourceItem(
        source_key="douban_group_656297_tab_42899",
        external_id="topic-1",
        title="【闲置】渴望鸡粮",
        url="https://example.com/topic-1",
        source_type="douban_topic",
        reply_count=1,
        last_active_text="03-28 18:56",
        summary="初始摘要",
    )
    updated = item.model_copy(update={"reply_count": 9, "last_active_text": "03-29 09:00"})

    repository.upsert_items(item.source_key, "label", [item], requested_items=1)
    sync = repository.upsert_items(item.source_key, "label", [updated], requested_items=1)

    assert sync.updated == 1
    assert sync.reevaluated_existing == 1
    assert sync.reevaluate_item_ids == ["topic-1"]


def test_storage_upsert_detail(tmp_path) -> None:
    repository = SourceItemRepository(db_path=tmp_path / "test-detail.db")
    detail = SourceItemDetail(
        source_key="douban_group_656297_tab_42899",
        external_id="482306083",
        status="ok",
        body_text="详细正文",
        image_urls=["https://img.example.com/1.jpg"],
        fetched_at="2026-03-28T00:00:00+00:00",
    )

    repository.upsert_detail(detail)
    loaded = repository.get_detail(detail.source_key, detail.external_id)

    assert loaded is not None
    assert loaded.status == "ok"
    assert loaded.body_text == "详细正文"


def test_storage_pagination_stats_and_audit(tmp_path) -> None:
    repository = SourceItemRepository(db_path=tmp_path / "test-page.db")
    for idx in range(5):
        repository.upsert_items(
            "douban_group_656297_tab_42899",
            "label",
            [
                SourceItem(
                    source_key="douban_group_656297_tab_42899",
                    external_id=f"topic-{idx}",
                    title=f"title-{idx}",
                    url=f"https://example.com/{idx}",
                    source_type="douban_topic",
                )
            ],
            requested_items=1,
        )
    page, total = repository.list_items_page(source_key="douban_group_656297_tab_42899", offset=2, limit=2)
    repository.write_sync_run(
        source_key="douban_group_656297_tab_42899",
        status="ok",
        requested_items=3,
        fetched_items=3,
        inserted_items=2,
        updated_items=1,
        matched_items=1,
        notifications_sent=1,
        notifications_failed=0,
    )
    repository.write_config_audit(
        entity_type="source",
        entity_key="douban_group_656297_tab_42899",
        action="update",
        actor="webui",
        file_name="douban.yaml",
        before_payload={"enabled": True},
        after_payload={"enabled": False},
    )
    stats = repository.summarize_last_24h()
    audits, audit_total = repository.list_config_audit(limit=10)

    assert total == 5
    assert len(page) == 2
    assert stats.sync_runs == 1
    assert stats.inserted_items == 2
    assert stats.matched_items == 1
    assert audit_total == 1
    assert audits[0].entity_key == "douban_group_656297_tab_42899"
