from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import yaml

from app.core.settings import get_settings
from app.models.config import RuleConfig, RuleConfigUpdate, SourceConfig, SourceConfigUpdate


_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{2,79}$")
_FILE_RE = re.compile(r"^[A-Za-z0-9._-]+\.ya?ml$")


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML file must contain a mapping at top level: {path}")
    return data


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, allow_unicode=True, sort_keys=False)


def _clean_list(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    cleaned = [str(value).strip() for value in values if str(value).strip()]
    return cleaned


def _validate_key(value: str, *, field_name: str) -> None:
    if not _KEY_RE.fullmatch(value):
        raise ValueError(f"{field_name} must use 3-80 chars: lowercase letters, digits, underscore, hyphen.")


def _validate_file_name(file_name: str) -> None:
    if not _FILE_RE.fullmatch(file_name) or "/" in file_name or ".." in file_name:
        raise ValueError("file_name must be a safe .yaml filename without path separators.")


def _validate_source_config(source: SourceConfig) -> None:
    _validate_key(source.source_key, field_name="source_key")
    if source.interval_minutes is not None and not (1 <= source.interval_minutes <= 1440):
        raise ValueError("interval_minutes must be between 1 and 1440.")
    if source.max_items is not None and not (1 <= source.max_items <= 50):
        raise ValueError("max_items must be between 1 and 50.")
    if source.pages is not None and not (1 <= source.pages <= 20):
        raise ValueError("pages must be between 1 and 20.")


def _validate_rule_config(rule: RuleConfig) -> None:
    _validate_key(rule.rule_key, field_name="rule_key")
    if rule.notify.cooldown_hours < 1 or rule.notify.cooldown_hours > 24 * 30:
        raise ValueError("notify.cooldown_hours must be between 1 and 720.")
    if rule.price and rule.price.min_cny is not None and rule.price.min_cny < 0:
        raise ValueError("price.min_cny must be non-negative.")
    if rule.price and rule.price.max_cny is not None and rule.price.max_cny < 0:
        raise ValueError("price.max_cny must be non-negative.")
    if rule.price and rule.price.min_cny is not None and rule.price.max_cny is not None and rule.price.min_cny > rule.price.max_cny:
        raise ValueError("price.min_cny must be less than or equal to price.max_cny.")
    if rule.spec and rule.spec.value_g is not None and rule.spec.value_g < 0:
        raise ValueError("spec.value_g must be non-negative.")


class ConfigEditor:
    def __init__(self, *, sources_dir: Path | None = None, rules_dir: Path | None = None) -> None:
        settings = get_settings()
        self.sources_dir = sources_dir or settings.sources_dir
        self.rules_dir = rules_dir or settings.rules_dir

    def update_source(self, source_key: str, payload: SourceConfigUpdate) -> SourceConfig:
        updates = payload.model_dump(exclude_none=True)
        if "keywords" in updates:
            updates["keywords"] = _clean_list(updates["keywords"]) or []
        if "notes" in updates:
            updates["notes"] = _clean_list(updates["notes"]) or []

        for path in sorted(self.sources_dir.glob("*.yaml")):
            data = _read_yaml(path)
            sources = data.get("sources")
            if not isinstance(sources, list):
                continue
            for idx, raw in enumerate(sources):
                if not isinstance(raw, dict):
                    continue
                if raw.get("source_key") != source_key:
                    continue
                merged = dict(raw)
                merged.update(updates)
                source = SourceConfig.model_validate(merged)
                _validate_source_config(source)
                sources[idx] = source.model_dump(exclude_none=True)
                _write_yaml(path, data)
                return source
        raise KeyError(f"Unknown source key: {source_key}")

    def create_source(self, file_name: str, payload: SourceConfig) -> SourceConfig:
        _validate_file_name(file_name)
        _validate_source_config(payload)
        path = self.sources_dir / file_name
        data = _read_yaml(path) if path.exists() else {"sources": []}
        sources = data.get("sources")
        if not isinstance(sources, list):
            raise ValueError(f"Invalid sources file structure: {path}")
        if any(isinstance(raw, dict) and raw.get("source_key") == payload.source_key for raw in sources):
            raise ValueError(f"Source key already exists in {path.name}: {payload.source_key}")
        sources.append(payload.model_dump(exclude_none=True))
        data["sources"] = sources
        self.sources_dir.mkdir(parents=True, exist_ok=True)
        _write_yaml(path, data)
        return payload

    def duplicate_source(self, source_key: str, *, new_key: str, file_name: str | None = None) -> SourceConfig:
        _validate_key(new_key, field_name="source_key")
        for path in sorted(self.sources_dir.glob("*.yaml")):
            data = _read_yaml(path)
            sources = data.get("sources")
            if not isinstance(sources, list):
                continue
            for raw in sources:
                if not isinstance(raw, dict):
                    continue
                if raw.get("source_key") != source_key:
                    continue
                duplicated = dict(raw)
                duplicated["source_key"] = new_key
                if duplicated.get("label"):
                    duplicated["label"] = f'{duplicated["label"]}（副本）'
                target_file = file_name or path.name
                return self.create_source(target_file, SourceConfig.model_validate(duplicated))
        raise KeyError(f"Unknown source key: {source_key}")

    def delete_source(self, source_key: str) -> None:
        for path in sorted(self.sources_dir.glob("*.yaml")):
            data = _read_yaml(path)
            sources = data.get("sources")
            if not isinstance(sources, list):
                continue
            filtered = [raw for raw in sources if not (isinstance(raw, dict) and raw.get("source_key") == source_key)]
            if len(filtered) == len(sources):
                continue
            data["sources"] = filtered
            _write_yaml(path, data)
            return
        raise KeyError(f"Unknown source key: {source_key}")

    def update_rule(self, rule_key: str, payload: RuleConfigUpdate) -> RuleConfig:
        updates = payload.model_dump(exclude_none=True)
        for key in ("sources", "include_keywords", "alias_keywords", "exclude_keywords"):
            if key in updates:
                updates[key] = _clean_list(updates[key]) or []

        if "spec" in updates and updates["spec"] is not None:
            spec = updates["spec"]
            if isinstance(spec, dict) and "aliases" in spec:
                spec["aliases"] = _clean_list(spec["aliases"]) or []
        for path in sorted(self.rules_dir.glob("*.yaml")):
            data = _read_yaml(path)
            rules = data.get("rules")
            if not isinstance(rules, list):
                continue
            for idx, raw in enumerate(rules):
                if not isinstance(raw, dict):
                    continue
                if raw.get("rule_key") != rule_key:
                    continue
                merged = dict(raw)
                merged.update(updates)
                rule = RuleConfig.model_validate(merged)
                _validate_rule_config(rule)
                rules[idx] = rule.model_dump(exclude_none=True)
                _write_yaml(path, data)
                return rule
        raise KeyError(f"Unknown rule key: {rule_key}")

    def create_rule(self, file_name: str, payload: RuleConfig) -> RuleConfig:
        _validate_file_name(file_name)
        _validate_rule_config(payload)
        path = self.rules_dir / file_name
        data = _read_yaml(path) if path.exists() else {"rules": []}
        rules = data.get("rules")
        if not isinstance(rules, list):
            raise ValueError(f"Invalid rules file structure: {path}")
        if any(isinstance(raw, dict) and raw.get("rule_key") == payload.rule_key for raw in rules):
            raise ValueError(f"Rule key already exists in {path.name}: {payload.rule_key}")
        rules.append(payload.model_dump(exclude_none=True))
        data["rules"] = rules
        self.rules_dir.mkdir(parents=True, exist_ok=True)
        _write_yaml(path, data)
        return payload

    def duplicate_rule(self, rule_key: str, *, new_key: str, file_name: str | None = None) -> RuleConfig:
        _validate_key(new_key, field_name="rule_key")
        for path in sorted(self.rules_dir.glob("*.yaml")):
            data = _read_yaml(path)
            rules = data.get("rules")
            if not isinstance(rules, list):
                continue
            for raw in rules:
                if not isinstance(raw, dict):
                    continue
                if raw.get("rule_key") != rule_key:
                    continue
                duplicated = dict(raw)
                duplicated["rule_key"] = new_key
                target_file = file_name or path.name
                return self.create_rule(target_file, RuleConfig.model_validate(duplicated))
        raise KeyError(f"Unknown rule key: {rule_key}")

    def delete_rule(self, rule_key: str) -> None:
        for path in sorted(self.rules_dir.glob("*.yaml")):
            data = _read_yaml(path)
            rules = data.get("rules")
            if not isinstance(rules, list):
                continue
            filtered = [raw for raw in rules if not (isinstance(raw, dict) and raw.get("rule_key") == rule_key)]
            if len(filtered) == len(rules):
                continue
            data["rules"] = filtered
            _write_yaml(path, data)
            return
        raise KeyError(f"Unknown rule key: {rule_key}")
