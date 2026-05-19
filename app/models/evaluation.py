from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CandidateInput(BaseModel):
    source_key: str
    external_id: str | None = None
    title: str = ""
    body: str = ""
    url: str | None = None


class PriceCandidate(BaseModel):
    raw_text: str
    amount_cny: float
    source_field: str


class SpecCandidate(BaseModel):
    raw_text: str
    total_grams: int
    source_field: str
    expression_type: str


class ExtractionResult(BaseModel):
    source_key: str
    include_keyword_hits: list[str] = Field(default_factory=list)
    exclude_keyword_hits: list[str] = Field(default_factory=list)
    price_candidates: list[PriceCandidate] = Field(default_factory=list)
    spec_candidates: list[SpecCandidate] = Field(default_factory=list)
    text_preview: str = ""


class RuleMatchResult(BaseModel):
    rule_key: str
    matched: bool
    priority: str
    reason: str
    matched_keywords: list[str] = Field(default_factory=list)
    excluded_keywords: list[str] = Field(default_factory=list)
    used_price: PriceCandidate | None = None
    used_spec: SpecCandidate | None = None
    checks: dict[str, Any] = Field(default_factory=dict)


class EvaluationResponse(BaseModel):
    candidate: CandidateInput
    extraction: ExtractionResult
    matches: list[RuleMatchResult]


class StoredEvaluationRecord(BaseModel):
    source_key: str
    external_id: str
    rule_key: str
    matched: bool
    priority: str
    reason: str
    matched_keywords: list[str] = Field(default_factory=list)
    excluded_keywords: list[str] = Field(default_factory=list)
    used_price_amount: float | None = None
    used_spec_grams: int | None = None
    evaluated_at: str
    created_at: str
    updated_at: str


class EvaluationSyncResponse(BaseModel):
    source_key: str
    requested_items: int
    fetched_items: int
    inserted: int
    updated: int
    evaluated_new_items: int
    reevaluated_existing_items: int = 0
    matched_items: int = 0
    evaluation_records_written: int
    notifications_attempted: int = 0
    notifications_sent: int = 0
    notifications_skipped: int = 0
    skipped_reason: str | None = None
    item_ids: list[str] = Field(default_factory=list)


class NotificationRecord(BaseModel):
    source_key: str
    external_id: str
    rule_key: str
    channel: str
    target: str
    status: str
    title: str
    content: str
    link_url: str | None = None
    created_at: str
    updated_at: str
    error_message: str | None = None


class MatchedItemRecord(BaseModel):
    source_key: str
    external_id: str
    source_type: str
    rule_key: str
    title: str
    url: str
    matched: bool
    reason: str
    used_price_amount: float | None = None
    used_spec_grams: int | None = None
    evaluated_at: str
    last_seen_at: str
    seen_count: int


class SourceHealthRecord(BaseModel):
    source_key: str
    status: str
    last_attempt_at: str
    last_success_at: str | None = None
    consecutive_failures: int = 0
    fetched_items: int = 0
    inserted_items: int = 0
    updated_items: int = 0
    last_error: str | None = None
    paused: bool = False
    pause_reason: str | None = None
    backoff_until: str | None = None
    updated_at: str


class SyncStats24h(BaseModel):
    sync_runs: int = 0
    inserted_items: int = 0
    updated_items: int = 0
    matched_items: int = 0
    notifications_sent: int = 0
    notifications_failed: int = 0
    source_errors: int = 0


class ConfigAuditRecord(BaseModel):
    entity_type: str
    entity_key: str
    action: str
    actor: str
    file_name: str | None = None
    before_payload: dict[str, Any] | None = None
    after_payload: dict[str, Any] | None = None
    created_at: str
