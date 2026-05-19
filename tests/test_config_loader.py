from app.services.config_loader import load_config_snapshot, reload_config_snapshot


def test_config_snapshot_contains_expected_sources_and_rules() -> None:
    snapshot = reload_config_snapshot()

    source_keys = {item.source_key for item in snapshot.sources}
    rule_keys = {item.rule_key for item in snapshot.rules}

    assert "douban_group_656297_tab_42899" in source_keys
    assert "smzdm_keywords_primary" in source_keys
    assert "smzdm_jd_chicken_breast" in source_keys
    assert "orijen_cat_5_4kg" in rule_keys
    assert "oralb_io3" in rule_keys
    assert "acana_cat_5_4kg" in rule_keys
    assert "instinct_high_protein_4_5kg" in rule_keys


def test_config_snapshot_summary_is_consistent() -> None:
    snapshot = load_config_snapshot()
    summary = snapshot.as_summary()

    assert summary["source_count"] >= 5
    assert summary["rule_count"] >= 2
    assert summary["enabled_sources"] <= summary["source_count"]
    assert summary["enabled_rules"] <= summary["rule_count"]
