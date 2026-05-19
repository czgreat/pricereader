from __future__ import annotations

from app.models.config import ConfigSnapshot, RuleConfig
from app.models.evaluation import CandidateInput, EvaluationResponse, ExtractionResult, RuleMatchResult
from app.services.config_loader import load_config_snapshot
from app.services.extractors import extract_price_candidates, extract_spec_candidates


def _unique_hits(text: str, keywords: list[str]) -> list[str]:
    haystack = text.casefold()
    hits: list[str] = []
    for keyword in keywords:
        if keyword.casefold() in haystack:
            hits.append(keyword)
    return hits


def _build_extraction(candidate: CandidateInput, snapshot: ConfigSnapshot) -> ExtractionResult:
    text_parts = [candidate.title.strip(), candidate.body.strip()]
    combined = "\n".join(part for part in text_parts if part)
    include_pool: list[str] = []
    exclude_pool: list[str] = []
    for rule in snapshot.rules:
        include_pool.extend(rule.include_keywords)
        include_pool.extend(rule.alias_keywords)
        exclude_pool.extend(rule.exclude_keywords)

    prices = []
    specs = []
    if candidate.title:
        prices.extend(extract_price_candidates(candidate.title, source_field="title"))
        specs.extend(extract_spec_candidates(candidate.title, source_field="title"))
    if candidate.body:
        prices.extend(extract_price_candidates(candidate.body, source_field="body"))
        specs.extend(extract_spec_candidates(candidate.body, source_field="body"))

    return ExtractionResult(
        source_key=candidate.source_key,
        include_keyword_hits=sorted(set(_unique_hits(combined, include_pool))),
        exclude_keyword_hits=sorted(set(_unique_hits(combined, exclude_pool))),
        price_candidates=prices,
        spec_candidates=specs,
        text_preview=combined[:500],
    )


def _spec_match(rule: RuleConfig, extraction: ExtractionResult, combined_text: str):
    if not rule.spec:
        return True, None

    if rule.spec.mode == "model":
        hits = _unique_hits(combined_text, rule.spec.aliases)
        return bool(hits), None

    if rule.spec.value_g is None:
        return False, None

    for item in extraction.spec_candidates:
        if item.total_grams == rule.spec.value_g:
            return True, item

    alias_hits = _unique_hits(combined_text, rule.spec.aliases)
    return bool(alias_hits), None


def _price_match(rule: RuleConfig, extraction: ExtractionResult):
    if not rule.price or (rule.price.min_cny is None and rule.price.max_cny is None):
        return True, None

    for item in extraction.price_candidates:
        if rule.price.min_cny is not None and item.amount_cny < rule.price.min_cny:
            continue
        if rule.price.max_cny is not None and item.amount_cny > rule.price.max_cny:
            continue
        return True, item
    return False, None


def evaluate_candidate(candidate: CandidateInput, snapshot: ConfigSnapshot | None = None) -> EvaluationResponse:
    config_snapshot = snapshot or load_config_snapshot()
    extraction = _build_extraction(candidate, config_snapshot)
    combined_text = "\n".join(part for part in [candidate.title, candidate.body] if part)
    results: list[RuleMatchResult] = []

    for rule in config_snapshot.rules:
        if not rule.enabled:
            continue

        source_ok = not rule.sources or candidate.source_key in rule.sources
        include_hits = _unique_hits(combined_text, rule.include_keywords + rule.alias_keywords)
        exclude_hits = _unique_hits(combined_text, rule.exclude_keywords)
        keywords_ok = bool(include_hits)
        exclude_ok = not exclude_hits
        spec_ok, used_spec = _spec_match(rule, extraction, combined_text)
        price_ok, used_price = _price_match(rule, extraction)

        matched = all((source_ok, keywords_ok, exclude_ok, spec_ok, price_ok))
        reason = "matched" if matched else "filtered"
        if not source_ok:
            reason = "source_not_allowed"
        elif not keywords_ok:
            reason = "missing_keywords"
        elif not exclude_ok:
            reason = "excluded_keyword_hit"
        elif not spec_ok:
            reason = "spec_not_matched"
        elif not price_ok:
            reason = "price_not_matched"

        results.append(
            RuleMatchResult(
                rule_key=rule.rule_key,
                matched=matched,
                priority=rule.priority,
                reason=reason,
                matched_keywords=include_hits,
                excluded_keywords=exclude_hits,
                used_price=used_price,
                used_spec=used_spec,
                checks={
                    "source_ok": source_ok,
                    "keywords_ok": keywords_ok,
                    "exclude_ok": exclude_ok,
                    "spec_ok": spec_ok,
                    "price_ok": price_ok,
                },
            )
        )

    return EvaluationResponse(
        candidate=candidate,
        extraction=extraction,
        matches=results,
    )
