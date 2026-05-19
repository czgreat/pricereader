from pathlib import Path

import yaml

from app.services.config_editor import ConfigEditor
from app.models.config import RuleConfig, RuleConfigUpdate, SourceConfig, SourceConfigUpdate


def test_update_source_config_persists_yaml(tmp_path) -> None:
    sources_dir = tmp_path / "sources"
    sources_dir.mkdir()
    path = sources_dir / "smzdm.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "sources": [
                    {
                        "source_key": "smzdm_keywords_primary",
                        "enabled": True,
                        "label": "什么值得买 / 官方RSS",
                        "feed_url": "http://feed.smzdm.com",
                        "interval_minutes": 8,
                        "keywords": ["渴望 猫粮 5.4kg"],
                    }
                ]
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    editor = ConfigEditor(sources_dir=sources_dir, rules_dir=tmp_path / "rules")
    updated = editor.update_source(
        "smzdm_keywords_primary",
        SourceConfigUpdate(
            enabled=False,
            interval_minutes=15,
            keywords=["欧乐B io3", "渴望 猫粮 5.4kg"],
            notes=["n1", "n2"],
        ),
    )

    saved = yaml.safe_load(path.read_text(encoding="utf-8"))
    source = saved["sources"][0]
    assert updated.enabled is False
    assert source["interval_minutes"] == 15
    assert source["keywords"] == ["欧乐B io3", "渴望 猫粮 5.4kg"]
    assert source["notes"] == ["n1", "n2"]


def test_update_rule_config_persists_yaml(tmp_path) -> None:
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    path = rules_dir / "default.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "rules": [
                    {
                        "rule_key": "oralb_io3",
                        "enabled": True,
                        "priority": "P1",
                        "sources": ["smzdm_keywords_primary"],
                        "include_keywords": ["欧乐B"],
                        "alias_keywords": [],
                        "exclude_keywords": ["刷头"],
                        "price": {"mode": "final_payable", "min_cny": 250, "max_cny": 350},
                        "notify": {"cooldown_hours": 24},
                    }
                ]
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    editor = ConfigEditor(sources_dir=tmp_path / "sources", rules_dir=rules_dir)
    updated = editor.update_rule(
        "oralb_io3",
        RuleConfigUpdate(
            priority="P2",
            include_keywords=["欧乐B", "iO3"],
            price={"mode": "final_payable", "min_cny": 269, "max_cny": 329},
            notify={"cooldown_hours": 12},
        ),
    )

    saved = yaml.safe_load(path.read_text(encoding="utf-8"))
    rule = saved["rules"][0]
    assert updated.priority == "P2"
    assert rule["include_keywords"] == ["欧乐B", "iO3"]
    assert rule["price"]["min_cny"] == 269
    assert rule["price"]["max_cny"] == 329
    assert rule["notify"]["cooldown_hours"] == 12


def test_update_rule_config_rejects_price_range_inversion(tmp_path) -> None:
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    path = rules_dir / "default.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "rules": [
                    {
                        "rule_key": "oralb_io3",
                        "enabled": True,
                        "priority": "P1",
                        "sources": ["smzdm_keywords_primary"],
                        "include_keywords": ["欧乐B"],
                        "exclude_keywords": ["刷头"],
                        "price": {"mode": "final_payable", "max_cny": 350},
                        "notify": {"cooldown_hours": 24},
                    }
                ]
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    editor = ConfigEditor(sources_dir=tmp_path / "sources", rules_dir=rules_dir)
    try:
        editor.update_rule(
            "oralb_io3",
            RuleConfigUpdate(
                price={"mode": "final_payable", "min_cny": 400, "max_cny": 300},
            ),
        )
    except ValueError as exc:
        assert "price.min_cny" in str(exc)
    else:
        raise AssertionError("Expected validation error")


def test_create_and_delete_source_config(tmp_path) -> None:
    sources_dir = tmp_path / "sources"
    sources_dir.mkdir()
    editor = ConfigEditor(sources_dir=sources_dir, rules_dir=tmp_path / "rules")

    created = editor.create_source(
        "custom.yaml",
        SourceConfig.model_validate(
            {
                "source_key": "custom_source",
                "enabled": True,
                "label": "自定义来源",
                "url": "https://example.com/feed",
                "interval_minutes": 30,
                "keywords": ["demo"],
            }
        ),
    )

    payload = yaml.safe_load((sources_dir / "custom.yaml").read_text(encoding="utf-8"))
    assert created.source_key == "custom_source"
    assert payload["sources"][0]["source_key"] == "custom_source"

    editor.delete_source("custom_source")
    payload = yaml.safe_load((sources_dir / "custom.yaml").read_text(encoding="utf-8"))
    assert payload["sources"] == []


def test_create_and_delete_rule_config(tmp_path) -> None:
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    editor = ConfigEditor(sources_dir=tmp_path / "sources", rules_dir=rules_dir)

    created = editor.create_rule(
        "custom.yaml",
        RuleConfig.model_validate(
            {
                "rule_key": "custom_rule",
                "enabled": True,
                "priority": "P2",
                "sources": ["smzdm_keywords_primary"],
                "include_keywords": ["demo"],
                "exclude_keywords": [],
                "notify": {"cooldown_hours": 6},
            }
        ),
    )

    payload = yaml.safe_load((rules_dir / "custom.yaml").read_text(encoding="utf-8"))
    assert created.rule_key == "custom_rule"
    assert payload["rules"][0]["rule_key"] == "custom_rule"

    editor.delete_rule("custom_rule")
    payload = yaml.safe_load((rules_dir / "custom.yaml").read_text(encoding="utf-8"))
    assert payload["rules"] == []


def test_create_rule_defaults_cooldown_to_2_hours(tmp_path) -> None:
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    editor = ConfigEditor(sources_dir=tmp_path / "sources", rules_dir=rules_dir)

    created = editor.create_rule(
        "custom.yaml",
        RuleConfig.model_validate(
            {
                "rule_key": "custom_rule_default_cooldown",
                "enabled": True,
                "sources": ["smzdm_keywords_primary"],
                "include_keywords": ["demo"],
            }
        ),
    )

    payload = yaml.safe_load((rules_dir / "custom.yaml").read_text(encoding="utf-8"))
    assert created.notify.cooldown_hours == 2
    assert payload["rules"][0]["notify"]["cooldown_hours"] == 2


def test_config_editor_validates_source_key_and_file_name(tmp_path) -> None:
    editor = ConfigEditor(sources_dir=tmp_path / "sources", rules_dir=tmp_path / "rules")
    (tmp_path / "sources").mkdir()

    try:
        editor.create_source(
            "../bad.yaml",
            SourceConfig.model_validate(
                {
                    "source_key": "BAD KEY",
                    "label": "bad",
                }
            ),
        )
    except ValueError as exc:
        assert "file_name" in str(exc) or "source_key" in str(exc)
    else:
        raise AssertionError("Expected validation error")


def test_duplicate_source_and_rule(tmp_path) -> None:
    sources_dir = tmp_path / "sources"
    rules_dir = tmp_path / "rules"
    sources_dir.mkdir()
    rules_dir.mkdir()
    (sources_dir / "base.yaml").write_text(
        yaml.safe_dump(
            {
                "sources": [
                    {"source_key": "base_source", "label": "基础来源", "enabled": True}
                ]
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (rules_dir / "base.yaml").write_text(
        yaml.safe_dump(
            {
                "rules": [
                    {"rule_key": "base_rule", "enabled": True, "sources": ["base_source"]}
                ]
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    editor = ConfigEditor(sources_dir=sources_dir, rules_dir=rules_dir)

    duplicated_source = editor.duplicate_source("base_source", new_key="base_source_copy")
    duplicated_rule = editor.duplicate_rule("base_rule", new_key="base_rule_copy")

    assert duplicated_source.source_key == "base_source_copy"
    assert duplicated_rule.rule_key == "base_rule_copy"
