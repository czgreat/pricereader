from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.adapters.douban_group import DoubanGroupAdapter
from app.adapters.smzdm_feed import SmzdmFeedAdapter
from app.api.settings_page import SETTINGS_PAGE_PATH
from app.core.settings import get_settings
from app.models.config import RuleConfig, RuleConfigUpdate, SourceConfig, SourceConfigUpdate
from app.models.evaluation import ConfigAuditRecord, SyncStats24h
from app.models.controls import ItemMuteUpdate, SourceControlUpdate
from app.models.evaluation import CandidateInput, EvaluationResponse
from app.models.evaluation import EvaluationSyncResponse
from app.models.runtime_config import RuntimeConfigPayload, RuntimeConfigViewPayload
from app.models.source_items import SourceFetchResponse, SourceItemDetail, StoredItem, SyncResponse
from app.services.config_editor import ConfigEditor
from app.services.config_loader import load_config_snapshot, reload_config_snapshot
from app.services.ingestion import sync_and_evaluate_new_items
from app.services.ingestion import sync_all_enabled_sources
from app.services.rule_engine import evaluate_candidate
from app.services.runtime_config import RuntimeConfigStore
from app.services.storage import SourceItemRepository
from app.tasks.scheduler import reload_scheduler, scheduler_status

router = APIRouter(prefix="/api/v1")


def _get_source_or_404(source_key: str):
    snapshot = load_config_snapshot()
    source = snapshot.source_map().get(source_key)
    if source is None:
        raise HTTPException(status_code=404, detail=f"Unknown source key: {source_key}")
    return snapshot, source


def _assert_source_type(source_key: str, actual: str, expected: str) -> None:
    if expected not in actual:
        raise HTTPException(status_code=400, detail=f"Source {source_key} is not a {expected} source.")


def _resolve_max_items(source, requested: int | None, default: int = 3) -> int:
    if requested is not None:
        return requested
    if source.max_items is not None:
        return source.max_items
    return default


def _get_rule_or_404(rule_key: str):
    snapshot = load_config_snapshot()
    rule = next((item for item in snapshot.rules if item.rule_key == rule_key), None)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"Unknown rule key: {rule_key}")
    return snapshot, rule


def _redact_runtime_payload(payload: RuntimeConfigPayload) -> dict[str, str]:
    def _masked(value: str) -> str:
        if not value:
            return ""
        if len(value) <= 8:
            return "••••••••"
        return f"{value[:2]}••••••{value[-2:]}"

    return {
        "wechat_push_url": payload.wechat_push_url,
        "douban_cookie": _masked(payload.douban_cookie),
        "smzdm_cookie": _masked(payload.smzdm_cookie),
        "wechat_push_token": _masked(payload.wechat_push_token),
        "wechat_target_id": _masked(payload.wechat_target_id),
    }


@router.get("/summary")
def summary() -> dict[str, object]:
    settings = get_settings()
    snapshot = load_config_snapshot()
    runtime = RuntimeConfigStore().load()
    repository = SourceItemRepository()
    return {
        "project": settings.project_name,
        "version": settings.app_version,
        "config": snapshot.as_summary(),
        "last_24h": repository.summarize_last_24h().model_dump(),
        "paths": {
            "sources_dir": str(settings.sources_dir),
            "rules_dir": str(settings.rules_dir),
            "sqlite_dir": str(settings.sqlite_dir),
            "media_dir": str(settings.media_dir),
        },
        "integrations": {
            "wechat_configured": bool(runtime.wechat_push_url and runtime.wechat_push_token and runtime.wechat_target_id),
            "smzdm_cookie_configured": bool(runtime.smzdm_cookie),
            "douban_cookie_configured": bool(runtime.douban_cookie),
        },
    }


@router.get("/ui/bootstrap")
def ui_bootstrap() -> dict[str, object]:
    repository = SourceItemRepository()
    snapshot = load_config_snapshot()
    runtime = RuntimeConfigStore().load_view(reveal=False)
    return {
        "summary": summary(),
        "runtime_config": runtime.model_dump(),
        "sources": [item.model_dump() for item in snapshot.sources],
        "rules": [item.model_dump() for item in snapshot.rules],
        "scheduler": scheduler_status(),
        "stats_24h": repository.summarize_last_24h().model_dump(),
        "source_health": [item.model_dump() for item in repository.list_source_health(limit=50)],
        "source_controls": [item.model_dump() for item in repository.list_source_controls(limit=50)],
        "muted_items": [item.model_dump() for item in repository.list_item_mutes(limit=50)],
    }


@router.get("/runtime-config", response_model=RuntimeConfigViewPayload)
def get_runtime_config(reveal: bool = False) -> RuntimeConfigViewPayload:
    return RuntimeConfigStore().load_view(reveal=reveal)


@router.put("/runtime-config", response_model=RuntimeConfigPayload)
def update_runtime_config(payload: RuntimeConfigPayload) -> RuntimeConfigPayload:
    repository = SourceItemRepository()
    store = RuntimeConfigStore()
    before = store.load()
    saved = store.save(payload)
    repository.write_config_audit(
        entity_type="runtime_config",
        entity_key="runtime",
        action="update",
        actor="webui",
        file_name="data/runtime/.env.local",
        before_payload=_redact_runtime_payload(before),
        after_payload=_redact_runtime_payload(saved),
    )
    return saved


@router.get("/settings", include_in_schema=False)
def runtime_settings_page() -> FileResponse:
    return FileResponse(SETTINGS_PAGE_PATH)


@router.post("/config/reload")
def reload_config() -> dict[str, object]:
    snapshot = reload_config_snapshot()
    scheduler = reload_scheduler()
    return {
        "reloaded": True,
        "summary": snapshot.as_summary(),
        "scheduler_running": scheduler.running,
    }


@router.get("/sources")
def list_sources() -> dict[str, object]:
    snapshot = load_config_snapshot()
    return {
        "items": [item.model_dump() for item in snapshot.sources],
        "total": len(snapshot.sources),
    }


@router.put("/sources/{source_key}/config")
def update_source_config(source_key: str, payload: SourceConfigUpdate) -> dict[str, object]:
    repository = SourceItemRepository()
    snapshot_before, source_before = _get_source_or_404(source_key)
    try:
        updated = ConfigEditor().update_source(source_key, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    snapshot = reload_config_snapshot()
    scheduler = reload_scheduler()
    repository.write_config_audit(
        entity_type="source",
        entity_key=source_key,
        action="update",
        actor="webui",
        file_name=next((path.name for path in snapshot_before.source_files if path.name), None),
        before_payload=source_before.model_dump(),
        after_payload=updated.model_dump(),
    )
    return {
        "updated": True,
        "source": updated.model_dump(),
        "summary": snapshot.as_summary(),
        "scheduler_running": scheduler.running,
    }


@router.post("/sources/config")
def create_source_config(file_name: str, payload: SourceConfig) -> dict[str, object]:
    repository = SourceItemRepository()
    try:
        created = ConfigEditor().create_source(file_name=file_name, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    snapshot = reload_config_snapshot()
    scheduler = reload_scheduler()
    repository.write_config_audit(
        entity_type="source",
        entity_key=created.source_key,
        action="create",
        actor="webui",
        file_name=file_name,
        before_payload=None,
        after_payload=created.model_dump(),
    )
    return {
        "created": True,
        "source": created.model_dump(),
        "summary": snapshot.as_summary(),
        "scheduler_running": scheduler.running,
    }


@router.delete("/sources/{source_key}/config")
def delete_source_config(source_key: str) -> dict[str, object]:
    repository = SourceItemRepository()
    snapshot, source = _get_source_or_404(source_key)
    referenced_by = [rule.rule_key for rule in snapshot.rules if source_key in rule.sources]
    if referenced_by:
        raise HTTPException(
            status_code=409,
            detail=f"Source {source_key} is still referenced by rules: {', '.join(referenced_by)}",
        )
    try:
        ConfigEditor().delete_source(source_key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    snapshot = reload_config_snapshot()
    scheduler = reload_scheduler()
    repository.write_config_audit(
        entity_type="source",
        entity_key=source_key,
        action="delete",
        actor="webui",
        file_name=None,
        before_payload=source.model_dump(),
        after_payload=None,
    )
    return {
        "deleted": True,
        "source_key": source_key,
        "summary": snapshot.as_summary(),
        "scheduler_running": scheduler.running,
    }


@router.get("/rules")
def list_rules() -> dict[str, object]:
    snapshot = load_config_snapshot()
    return {
        "items": [item.model_dump() for item in snapshot.rules],
        "total": len(snapshot.rules),
    }


@router.put("/rules/{rule_key}/config")
def update_rule_config(rule_key: str, payload: RuleConfigUpdate) -> dict[str, object]:
    repository = SourceItemRepository()
    _, rule_before = _get_rule_or_404(rule_key)
    try:
        updated = ConfigEditor().update_rule(rule_key, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    snapshot = reload_config_snapshot()
    scheduler = reload_scheduler()
    repository.write_config_audit(
        entity_type="rule",
        entity_key=rule_key,
        action="update",
        actor="webui",
        file_name=None,
        before_payload=rule_before.model_dump(),
        after_payload=updated.model_dump(),
    )
    return {
        "updated": True,
        "rule": updated.model_dump(),
        "summary": snapshot.as_summary(),
        "scheduler_running": scheduler.running,
    }


@router.post("/rules/config")
def create_rule_config(file_name: str, payload: RuleConfig) -> dict[str, object]:
    repository = SourceItemRepository()
    try:
        created = ConfigEditor().create_rule(file_name=file_name, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    snapshot = reload_config_snapshot()
    scheduler = reload_scheduler()
    repository.write_config_audit(
        entity_type="rule",
        entity_key=created.rule_key,
        action="create",
        actor="webui",
        file_name=file_name,
        before_payload=None,
        after_payload=created.model_dump(),
    )
    return {
        "created": True,
        "rule": created.model_dump(),
        "summary": snapshot.as_summary(),
        "scheduler_running": scheduler.running,
    }


@router.delete("/rules/{rule_key}/config")
def delete_rule_config(rule_key: str) -> dict[str, object]:
    repository = SourceItemRepository()
    _, rule = _get_rule_or_404(rule_key)
    history = repository.rule_history_counts(rule_key)
    if history["evaluation_records"] or history["notification_records"]:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Rule {rule_key} has history: "
                f"{history['evaluation_records']} evaluations, {history['notification_records']} notifications. "
                "Disable it instead of deleting."
            ),
        )
    try:
        ConfigEditor().delete_rule(rule_key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    snapshot = reload_config_snapshot()
    scheduler = reload_scheduler()
    repository.write_config_audit(
        entity_type="rule",
        entity_key=rule_key,
        action="delete",
        actor="webui",
        file_name=None,
        before_payload=rule.model_dump(),
        after_payload=None,
    )
    return {
        "deleted": True,
        "rule_key": rule_key,
        "summary": snapshot.as_summary(),
        "scheduler_running": scheduler.running,
    }


@router.get("/sources/douban/{source_key}/sample", response_model=SourceFetchResponse)
def fetch_douban_sample(source_key: str, max_items: int | None = None) -> SourceFetchResponse:
    _, source = _get_source_or_404(source_key)
    _assert_source_type(source_key, source.source_key, "douban")
    limit = _resolve_max_items(source, max_items, default=3)

    settings = get_settings()
    adapter = DoubanGroupAdapter()
    cookie = settings.douban_cookie if settings.douban_cookie else None
    return adapter.fetch_sample(source, cookie=cookie, max_items=limit)


@router.post("/sources/douban/{source_key}/sync", response_model=SyncResponse)
def sync_douban_sample(source_key: str, max_items: int | None = None) -> SyncResponse:
    _, source = _get_source_or_404(source_key)
    _assert_source_type(source_key, source.source_key, "douban")
    limit = _resolve_max_items(source, max_items, default=3)

    settings = get_settings()
    adapter = DoubanGroupAdapter()
    cookie = settings.douban_cookie if settings.douban_cookie else None
    response = adapter.fetch_sample(source, cookie=cookie, max_items=limit)
    repository = SourceItemRepository()
    return repository.upsert_items(response.source_key, response.source_label, response.items, response.requested_items)


@router.post("/sources/douban/{source_key}/topics/{external_id}/detail", response_model=SourceItemDetail)
def fetch_douban_detail(source_key: str, external_id: str) -> SourceItemDetail:
    repository = SourceItemRepository()
    items = repository.list_items(source_key=source_key, limit=100)
    target = next((item for item in items if item.external_id == external_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail=f"Stored item not found: {source_key}/{external_id}")

    settings = get_settings()
    adapter = DoubanGroupAdapter()
    detail = adapter.fetch_topic_detail(
        item=target,
        cookie=settings.douban_cookie if settings.douban_cookie else None,
    )
    repository.upsert_detail(detail)
    return detail


@router.get("/sources/smzdm/{source_key}/sample", response_model=SourceFetchResponse)
def fetch_smzdm_sample(source_key: str, max_items: int | None = None) -> SourceFetchResponse:
    _, source = _get_source_or_404(source_key)
    _assert_source_type(source_key, source.source_key, "smzdm")
    limit = _resolve_max_items(source, max_items, default=5)

    adapter = SmzdmFeedAdapter()
    return adapter.fetch_sample(source, max_items=limit)


@router.post("/sources/smzdm/{source_key}/sync", response_model=SyncResponse)
def sync_smzdm_sample(source_key: str, max_items: int | None = None) -> SyncResponse:
    _, source = _get_source_or_404(source_key)
    _assert_source_type(source_key, source.source_key, "smzdm")
    limit = _resolve_max_items(source, max_items, default=5)

    adapter = SmzdmFeedAdapter()
    response = adapter.fetch_sample(source, max_items=limit)
    repository = SourceItemRepository()
    return repository.upsert_items(response.source_key, response.source_label, response.items, response.requested_items)


@router.get("/stored-items")
def list_stored_items(source_key: str | None = None, offset: int = 0, limit: int = 20) -> dict[str, object]:
    repository = SourceItemRepository()
    items, total = repository.list_items_page(source_key=source_key, offset=offset, limit=limit)
    return {
        "items": [item.model_dump() for item in items],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/evaluations")
def list_evaluations(source_key: str | None = None, matched_only: bool = False, offset: int = 0, limit: int = 50) -> dict[str, object]:
    repository = SourceItemRepository()
    records, total = repository.list_evaluation_records_page(source_key=source_key, matched_only=matched_only, offset=offset, limit=limit)
    return {
        "items": [record.model_dump() for record in records],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/matches")
def list_matches(source_key: str | None = None, rule_key: str | None = None, offset: int = 0, limit: int = 50) -> dict[str, object]:
    repository = SourceItemRepository()
    records, total = repository.list_matched_items_page(source_key=source_key, rule_key=rule_key, offset=offset, limit=limit)
    return {
        "items": [record.model_dump() for record in records],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/notifications")
def list_notifications(source_key: str | None = None, rule_key: str | None = None, offset: int = 0, limit: int = 50) -> dict[str, object]:
    repository = SourceItemRepository()
    records, total = repository.list_notification_records_page(source_key=source_key, rule_key=rule_key, offset=offset, limit=limit)
    return {
        "items": [record.model_dump() for record in records],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/source-health")
def list_source_health(source_key: str | None = None, offset: int = 0, limit: int = 50) -> dict[str, object]:
    repository = SourceItemRepository()
    records, total = repository.list_source_health_page(source_key=source_key, offset=offset, limit=limit)
    return {
        "items": [record.model_dump() for record in records],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/source-controls")
def list_source_controls(offset: int = 0, limit: int = 100) -> dict[str, object]:
    repository = SourceItemRepository()
    records, total = repository.list_source_controls_page(offset=offset, limit=limit)
    return {
        "items": [record.model_dump() for record in records],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.put("/sources/{source_key}/pause")
def pause_source(source_key: str, payload: SourceControlUpdate) -> dict[str, object]:
    repository = SourceItemRepository()
    record = repository.set_source_paused(source_key=source_key, paused=True, reason=payload.reason)
    return {"updated": True, "record": record.model_dump()}


@router.put("/sources/{source_key}/resume")
def resume_source(source_key: str, payload: SourceControlUpdate) -> dict[str, object]:
    repository = SourceItemRepository()
    record = repository.set_source_paused(source_key=source_key, paused=False, reason=payload.reason)
    return {"updated": True, "record": record.model_dump()}


@router.get("/muted-items")
def list_muted_items(source_key: str | None = None, offset: int = 0, limit: int = 100) -> dict[str, object]:
    repository = SourceItemRepository()
    records, total = repository.list_item_mutes_page(source_key=source_key, offset=offset, limit=limit)
    return {
        "items": [record.model_dump() for record in records],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/items/{source_key}/{external_id}/detail-view")
def get_item_detail_view(source_key: str, external_id: str) -> dict[str, object]:
    repository = SourceItemRepository()
    bundle = repository.get_item_bundle(source_key, external_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail=f"Stored item not found: {source_key}/{external_id}")
    return bundle


@router.get("/stats/24h", response_model=SyncStats24h)
def get_stats_24h() -> SyncStats24h:
    repository = SourceItemRepository()
    return repository.summarize_last_24h()


@router.get("/config-audit")
def list_config_audit(entity_type: str | None = None, offset: int = 0, limit: int = 50) -> dict[str, object]:
    repository = SourceItemRepository()
    items, total = repository.list_config_audit(entity_type=entity_type, offset=offset, limit=limit)
    return {
        "items": [item.model_dump() for item in items],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.put("/items/{source_key}/{external_id}/mute")
def mute_item(source_key: str, external_id: str, payload: ItemMuteUpdate) -> dict[str, object]:
    repository = SourceItemRepository()
    record = repository.set_item_muted(source_key=source_key, external_id=external_id, muted=True, reason=payload.reason)
    return {"updated": True, "record": record.model_dump()}


@router.put("/items/{source_key}/{external_id}/unmute")
def unmute_item(source_key: str, external_id: str, payload: ItemMuteUpdate) -> dict[str, object]:
    repository = SourceItemRepository()
    record = repository.set_item_muted(source_key=source_key, external_id=external_id, muted=False, reason=payload.reason)
    return {"updated": True, "record": record.model_dump()}


@router.post("/sources/{source_key}/sync-evaluate", response_model=EvaluationSyncResponse)
def sync_evaluate_source(source_key: str, max_items: int | None = None) -> EvaluationSyncResponse:
    try:
        return sync_and_evaluate_new_items(source_key=source_key, max_items=max_items)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sources/{source_key}/retry-sync", response_model=EvaluationSyncResponse)
def retry_source_sync(source_key: str, max_items: int | None = None) -> EvaluationSyncResponse:
    try:
        return sync_and_evaluate_new_items(source_key=source_key, max_items=max_items)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sync/run-all", response_model=list[EvaluationSyncResponse])
def sync_run_all(max_items: int | None = None) -> list[EvaluationSyncResponse]:
    return sync_all_enabled_sources(max_items=max_items)


@router.get("/scheduler")
def get_scheduler_status() -> dict[str, object]:
    return scheduler_status()


@router.post("/evaluate", response_model=EvaluationResponse)
def evaluate(payload: CandidateInput) -> EvaluationResponse:
    return evaluate_candidate(payload)
@router.post("/sources/{source_key}/duplicate")
def duplicate_source_config(source_key: str, new_key: str, file_name: str | None = None) -> dict[str, object]:
    repository = SourceItemRepository()
    try:
        created = ConfigEditor().duplicate_source(source_key, new_key=new_key, file_name=file_name)
    except (KeyError, ValueError) as exc:
        status_code = 404 if isinstance(exc, KeyError) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    snapshot = reload_config_snapshot()
    scheduler = reload_scheduler()
    repository.write_config_audit(
        entity_type="source",
        entity_key=created.source_key,
        action="duplicate",
        actor="webui",
        file_name=file_name,
        before_payload={"copied_from": source_key},
        after_payload=created.model_dump(),
    )
    return {
        "duplicated": True,
        "source": created.model_dump(),
        "summary": snapshot.as_summary(),
        "scheduler_running": scheduler.running,
    }


@router.post("/rules/{rule_key}/duplicate")
def duplicate_rule_config(rule_key: str, new_key: str, file_name: str | None = None) -> dict[str, object]:
    repository = SourceItemRepository()
    try:
        created = ConfigEditor().duplicate_rule(rule_key, new_key=new_key, file_name=file_name)
    except (KeyError, ValueError) as exc:
        status_code = 404 if isinstance(exc, KeyError) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    snapshot = reload_config_snapshot()
    scheduler = reload_scheduler()
    repository.write_config_audit(
        entity_type="rule",
        entity_key=created.rule_key,
        action="duplicate",
        actor="webui",
        file_name=file_name,
        before_payload={"copied_from": rule_key},
        after_payload=created.model_dump(),
    )
    return {
        "duplicated": True,
        "rule": created.model_dump(),
        "summary": snapshot.as_summary(),
        "scheduler_running": scheduler.running,
    }
