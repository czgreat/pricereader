from __future__ import annotations

from app.core.settings import get_settings
from app.models.config import ConfigSnapshot
from app.models.source_items import SourceItem


def should_fetch_detail_for_item(item: SourceItem, snapshot: ConfigSnapshot) -> bool:
    if "douban" not in item.source_key:
        return False

    settings = get_settings()
    if not settings.douban_cookie:
        return False

    title = item.title.casefold()
    for rule in snapshot.rules:
        if not rule.enabled:
            continue
        if rule.sources and item.source_key not in rule.sources:
            continue
        keywords = [*rule.include_keywords, *rule.alias_keywords]
        if any(keyword.casefold() in title for keyword in keywords):
            return True
    return False

