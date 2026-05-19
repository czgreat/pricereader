from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SourceConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_key: str
    enabled: bool = True
    mode: str | None = None
    label: str | None = None
    url: str | None = None
    interval_minutes: int | None = None
    max_items: int | None = None
    pages: int | None = None
    cookie_mode: str | None = None
    require_cookie: bool = False
    keywords: list[str] = Field(default_factory=list)


class SpecCondition(BaseModel):
    model_config = ConfigDict(extra="allow")

    mode: str = "equivalent"
    value_g: int | None = None
    aliases: list[str] = Field(default_factory=list)


class PriceCondition(BaseModel):
    model_config = ConfigDict(extra="allow")

    mode: str = "final_payable"
    min_cny: float | None = None
    max_cny: float | None = None


class NotifyConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    cooldown_hours: int = 2


class RuleConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    rule_key: str
    enabled: bool = True
    priority: str = "P1"
    sources: list[str] = Field(default_factory=list)
    include_keywords: list[str] = Field(default_factory=list)
    alias_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    spec: SpecCondition | None = None
    price: PriceCondition | None = None
    notify: NotifyConfig = Field(default_factory=NotifyConfig)


class SourceConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool | None = None
    mode: str | None = None
    label: str | None = None
    url: str | None = None
    interval_minutes: int | None = None
    max_items: int | None = None
    pages: int | None = None
    cookie_mode: str | None = None
    require_cookie: bool | None = None
    keywords: list[str] | None = None
    feed_url: str | None = None
    notes: list[str] | None = None


class RuleConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool | None = None
    priority: str | None = None
    sources: list[str] | None = None
    include_keywords: list[str] | None = None
    alias_keywords: list[str] | None = None
    exclude_keywords: list[str] | None = None
    spec: SpecCondition | None = None
    price: PriceCondition | None = None
    notify: NotifyConfig | None = None


class SourceFilePayload(BaseModel):
    sources: list[SourceConfig] = Field(default_factory=list)


class RuleFilePayload(BaseModel):
    rules: list[RuleConfig] = Field(default_factory=list)


class ConfigSnapshot(BaseModel):
    source_files: list[Path]
    rule_files: list[Path]
    sources: list[SourceConfig]
    rules: list[RuleConfig]

    def source_map(self) -> dict[str, SourceConfig]:
        return {item.source_key: item for item in self.sources}

    def as_summary(self) -> dict[str, Any]:
        return {
            "source_count": len(self.sources),
            "rule_count": len(self.rules),
            "enabled_sources": sum(1 for item in self.sources if item.enabled),
            "enabled_rules": sum(1 for item in self.rules if item.enabled),
        }
