from app.services.storage import SourceItemRepository


def test_source_health_success_and_failure(tmp_path) -> None:
    repo = SourceItemRepository(db_path=tmp_path / "health.db")

    repo.mark_source_success(
        source_key="smzdm_keywords_primary",
        fetched_items=3,
        inserted_items=2,
        updated_items=1,
    )
    repo.mark_source_failure(
        source_key="douban_group_656297_tab_42899",
        error_message="403 forbidden",
    )

    records = repo.list_source_health(limit=10)
    by_key = {item.source_key: item for item in records}

    assert by_key["smzdm_keywords_primary"].status == "ok"
    assert by_key["smzdm_keywords_primary"].inserted_items == 2
    assert by_key["douban_group_656297_tab_42899"].status == "error"
    assert by_key["douban_group_656297_tab_42899"].consecutive_failures == 1


def test_source_health_enters_backoff_after_repeated_failures(tmp_path) -> None:
    repo = SourceItemRepository(db_path=tmp_path / "health-backoff.db")

    repo.mark_source_failure(source_key="smzdm_keywords_primary", error_message="boom-1", base_interval_minutes=8)
    repo.mark_source_failure(source_key="smzdm_keywords_primary", error_message="boom-2", base_interval_minutes=8)
    repo.mark_source_failure(source_key="smzdm_keywords_primary", error_message="boom-3", base_interval_minutes=8)

    record = repo.list_source_health(source_key="smzdm_keywords_primary", limit=1)[0]

    assert record.status == "backoff"
    assert record.consecutive_failures == 3
    assert record.backoff_until is not None
