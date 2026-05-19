from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.services.config_loader import load_config_snapshot
from app.core.settings import get_settings
from app.models.evaluation import EvaluationResponse
from app.models.source_items import SourceItem
from app.notifiers.wechat_gateway import WeChatGatewayNotifier, WeChatPushMessage
from app.services.runtime_config import RuntimeConfigStore
from app.services.storage import SourceItemRepository

logger = logging.getLogger(__name__)


def _build_message(item: SourceItem, rule_key: str, evaluation: EvaluationResponse, target_id: str) -> WeChatPushMessage:
    match = next(result for result in evaluation.matches if result.rule_key == rule_key)
    parts = [f"来源: {item.source_key}", f"规则: {rule_key}", f"标题: {item.title}"]
    if match.used_price:
        parts.append(f"价格: {match.used_price.amount_cny:.2f} 元")
    if match.used_spec:
        parts.append(f"规格: {match.used_spec.total_grams}g")
    parts.append(f"链接: {item.url}")

    return WeChatPushMessage(
        title=f"PriceReader 命中 {rule_key}",
        content="\n".join(parts),
        target_id=target_id,
        link_url=item.url,
    )


def notify_matches(item: SourceItem, evaluation: EvaluationResponse, repository: SourceItemRepository | None = None) -> tuple[int, int, int]:
    settings = get_settings()
    runtime = RuntimeConfigStore().load()
    push_url = runtime.wechat_push_url or settings.wechat_push_url
    push_token = runtime.wechat_push_token or settings.wechat_push_token
    target_id = runtime.wechat_target_id or settings.wechat_target_id
    matched = [record for record in evaluation.matches if record.matched]
    if not matched:
        return 0, 0, 0

    if not push_url or not target_id:
        logger.info("Skipping notifications for %s because WeChat settings are incomplete.", item.external_id)
        return len(matched), 0, 0

    repo = repository or SourceItemRepository()
    notifier = WeChatGatewayNotifier(
        push_url=push_url,
        token=push_token,
    )

    snapshot = load_config_snapshot()
    rule_map = {rule.rule_key: rule for rule in snapshot.rules}
    attempted = 0
    sent = 0
    skipped = 0
    for record in matched:
        if repo.is_item_muted(source_key=item.source_key, external_id=item.external_id):
            message = _build_message(item, record.rule_key, evaluation, target_id)
            repo.write_notification_record(
                source_key=item.source_key,
                external_id=item.external_id,
                rule_key=record.rule_key,
                channel="wechat_gateway",
                target=target_id,
                status="skipped_muted",
                title=message.title,
                content=message.content,
                link_url=message.link_url,
                error_message="Item is manually muted.",
            )
            skipped += 1
            continue

        cooldown_hours = rule_map.get(record.rule_key).notify.cooldown_hours if rule_map.get(record.rule_key) else 2
        since = (datetime.now(timezone.utc) - timedelta(hours=cooldown_hours)).isoformat()
        recent = repo.get_recent_sent_notification(
            source_key=item.source_key,
            external_id=item.external_id,
            rule_key=record.rule_key,
            target=target_id,
            since_iso=since,
        )
        message = _build_message(item, record.rule_key, evaluation, target_id)
        error_message = None
        status = "sent"
        if recent is not None:
            status = "skipped_cooldown"
            error_message = f"Recent notification exists within {cooldown_hours}h cooldown."
            skipped += 1
        else:
            attempted += 1
            try:
                notifier.send_sync(message)
                sent += 1
            except Exception as exc:  # pragma: no cover - exercised in integration paths
                status = "failed"
                error_message = str(exc)
                logger.exception("Failed to send WeChat notification for %s / %s", item.external_id, record.rule_key)

        repo.write_notification_record(
            source_key=item.source_key,
            external_id=item.external_id,
            rule_key=record.rule_key,
            channel="wechat_gateway",
            target=target_id,
            status=status,
            title=message.title,
            content=message.content,
            link_url=message.link_url,
            error_message=error_message,
        )

    return attempted, sent, skipped
