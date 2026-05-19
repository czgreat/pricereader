from __future__ import annotations

from datetime import datetime, timezone

from app.adapters.douban_group import DoubanGroupAdapter
from app.adapters.smzdm_feed import SmzdmFeedAdapter
from app.core.settings import get_settings
from app.models.evaluation import CandidateInput, EvaluationSyncResponse
from app.models.source_items import SourceFetchResponse
from app.services.config_loader import load_config_snapshot
from app.services.douban_enrichment import should_fetch_detail_for_item
from app.services.notification_service import notify_matches
from app.services.rule_engine import evaluate_candidate
from app.services.storage import SourceItemRepository


def _fetch_source_sample(source_key: str, max_items: int | None) -> SourceFetchResponse:
    snapshot = load_config_snapshot()
    source = snapshot.source_map().get(source_key)
    if source is None:
        raise ValueError(f"Unknown source key: {source_key}")
    limit = max_items if max_items is not None else (source.max_items or 3)

    if "douban" in source.source_key:
        settings = get_settings()
        adapter = DoubanGroupAdapter()
        cookie = settings.douban_cookie if settings.douban_cookie else None
        return adapter.fetch_sample(source, cookie=cookie, max_items=limit)

    if "smzdm" in source.source_key:
        adapter = SmzdmFeedAdapter()
        return adapter.fetch_sample(source, max_items=limit)

    raise ValueError(f"Unsupported source type for {source_key}")


def sync_and_evaluate_new_items(source_key: str, max_items: int | None = None) -> EvaluationSyncResponse:
    repository = SourceItemRepository()
    snapshot = load_config_snapshot()
    source = snapshot.source_map().get(source_key)
    if source is None:
        raise ValueError(f"Unknown source key: {source_key}")
    requested_items = max_items if max_items is not None else (source.max_items or 3)
    control = repository.get_source_control(source_key)
    if control and control.paused:
        result = EvaluationSyncResponse(
            source_key=source_key,
            requested_items=requested_items,
            fetched_items=0,
            inserted=0,
            updated=0,
            evaluated_new_items=0,
            matched_items=0,
            evaluation_records_written=0,
            notifications_attempted=0,
            notifications_sent=0,
            notifications_skipped=0,
            skipped_reason=f"source_paused: {control.reason or 'manual pause'}",
            item_ids=[],
        )
        repository.write_sync_run(
            source_key=source_key,
            status="paused",
            requested_items=requested_items,
            fetched_items=0,
            inserted_items=0,
            updated_items=0,
            matched_items=0,
            notifications_sent=0,
            notifications_failed=0,
            skipped_reason=result.skipped_reason,
        )
        return result
    health_record = next((item for item in repository.list_source_health(source_key=source_key, limit=1)), None)
    if health_record and health_record.backoff_until:
        if datetime.fromisoformat(health_record.backoff_until) > datetime.now(timezone.utc):
            result = EvaluationSyncResponse(
                source_key=source_key,
                requested_items=requested_items,
                fetched_items=0,
                inserted=0,
                updated=0,
                evaluated_new_items=0,
                reevaluated_existing_items=0,
                matched_items=0,
                evaluation_records_written=0,
                notifications_attempted=0,
                notifications_sent=0,
                notifications_skipped=0,
                skipped_reason=f"source_backoff_until: {health_record.backoff_until}",
                item_ids=[],
            )
            repository.write_sync_run(
                source_key=source_key,
                status="backoff",
                requested_items=requested_items,
                fetched_items=0,
                inserted_items=0,
                updated_items=0,
                matched_items=0,
                notifications_sent=0,
                notifications_failed=0,
                skipped_reason=result.skipped_reason,
            )
            return result

    try:
        response = _fetch_source_sample(source_key, requested_items)
        sync = repository.upsert_items(response.source_key, response.source_label, response.items, response.requested_items)
    except Exception as exc:
        repository.mark_source_failure(
            source_key=source_key,
            error_message=str(exc),
            base_interval_minutes=source.interval_minutes,
        )
        repository.write_sync_run(
            source_key=source_key,
            status="error",
            requested_items=requested_items,
            fetched_items=0,
            inserted_items=0,
            updated_items=0,
            matched_items=0,
            notifications_sent=0,
            notifications_failed=0,
            error_message=str(exc),
        )
        raise

    records_written = 0
    evaluated_items = 0
    notifications_attempted = 0
    notifications_sent = 0
    notifications_skipped = 0
    matched_items = 0
    settings = get_settings()
    douban_adapter = DoubanGroupAdapter()
    detail_attempts = 0
    reevaluate_ids = set(sync.reevaluate_item_ids)
    new_ids = set(sync.inserted_item_ids)
    candidates = [item for item in response.items if item.external_id in new_ids or item.external_id in reevaluate_ids]
    reevaluated_existing = 0
    evaluated_new_items = 0

    for item in candidates:
        if item.external_id in reevaluate_ids and item.external_id not in new_ids:
            reevaluated_existing += 1
        else:
            evaluated_new_items += 1
        evaluated_items += 1
        body = item.summary
        if should_fetch_detail_for_item(item, snapshot) and detail_attempts < 2:
            detail = douban_adapter.fetch_topic_detail(item, cookie=settings.douban_cookie)
            repository.upsert_detail(detail)
            detail_attempts += 1
            if detail.status == "ok" and detail.body_text:
                body = detail.body_text

        evaluation = evaluate_candidate(
            CandidateInput(
                source_key=item.source_key,
                external_id=item.external_id,
                title=item.title,
                body=body,
                url=item.url,
            )
        )
        records_written += repository.write_evaluation_records(item, evaluation)
        if any(match.matched for match in evaluation.matches):
            matched_items += 1
        attempted, sent, skipped = notify_matches(item, evaluation, repository=repository)
        notifications_attempted += attempted
        notifications_sent += sent
        notifications_skipped += skipped

    repository.mark_source_success(
        source_key=sync.source_key,
        fetched_items=sync.fetched_items,
        inserted_items=sync.inserted,
        updated_items=sync.updated,
    )
    repository.write_sync_run(
        source_key=sync.source_key,
        status="ok",
        requested_items=sync.requested_items,
        fetched_items=sync.fetched_items,
        inserted_items=sync.inserted,
        updated_items=sync.updated,
        matched_items=matched_items,
        notifications_sent=notifications_sent,
        notifications_failed=max(notifications_attempted - notifications_sent, 0),
        skipped_reason=None,
    )

    return EvaluationSyncResponse(
        source_key=sync.source_key,
        requested_items=sync.requested_items,
        fetched_items=sync.fetched_items,
        inserted=sync.inserted,
        updated=sync.updated,
        evaluated_new_items=evaluated_new_items,
        reevaluated_existing_items=reevaluated_existing,
        matched_items=matched_items,
        evaluation_records_written=records_written,
        notifications_attempted=notifications_attempted,
        notifications_sent=notifications_sent,
        notifications_skipped=notifications_skipped,
        item_ids=[item.external_id for item in response.items],
    )


def sync_all_enabled_sources(max_items: int | None = None) -> list[EvaluationSyncResponse]:
    snapshot = load_config_snapshot()
    results: list[EvaluationSyncResponse] = []
    for source in snapshot.sources:
        if not source.enabled:
            continue
        try:
            results.append(sync_and_evaluate_new_items(source.source_key, max_items=max_items))
        except Exception as exc:
            results.append(
                EvaluationSyncResponse(
                    source_key=source.source_key,
                    requested_items=max_items if max_items is not None else (source.max_items or 3),
                    fetched_items=0,
                    inserted=0,
                    updated=0,
                    evaluated_new_items=0,
                    reevaluated_existing_items=0,
                    matched_items=0,
                    evaluation_records_written=0,
                    notifications_attempted=0,
                    notifications_sent=0,
                    notifications_skipped=0,
                    skipped_reason=f"source_error: {exc}",
                    item_ids=[],
                )
            )
    return results
