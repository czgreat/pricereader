from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from app.core.settings import get_settings
from app.models.config import ConfigSnapshot, RuleFilePayload, SourceFilePayload


def _yaml_files(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return sorted(item for item in path.glob("*.yaml") if item.is_file())


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML file must contain a mapping at top level: {path}")
    return data


@lru_cache(maxsize=1)
def load_config_snapshot() -> ConfigSnapshot:
    settings = get_settings()
    source_files = _yaml_files(settings.sources_dir)
    rule_files = _yaml_files(settings.rules_dir)

    sources = []
    for path in source_files:
        payload = SourceFilePayload.model_validate(_load_yaml(path))
        sources.extend(payload.sources)

    rules = []
    for path in rule_files:
        payload = RuleFilePayload.model_validate(_load_yaml(path))
        rules.extend(payload.rules)

    return ConfigSnapshot(
        source_files=source_files,
        rule_files=rule_files,
        sources=sources,
        rules=rules,
    )


def reload_config_snapshot() -> ConfigSnapshot:
    load_config_snapshot.cache_clear()
    return load_config_snapshot()

