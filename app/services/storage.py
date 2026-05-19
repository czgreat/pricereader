from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import sqlite3
from pathlib import Path

from app.core.settings import get_settings
from app.models.controls import ItemMuteRecord, SourceControlRecord
from app.models.evaluation import ConfigAuditRecord, EvaluationResponse, MatchedItemRecord, NotificationRecord, SourceHealthRecord, StoredEvaluationRecord, SyncStats24h
from app.models.source_items import SourceItem, SourceItemDetail, StoredItem, SyncResponse


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS source_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key TEXT NOT NULL,
    external_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    author_name TEXT,
    author_url TEXT,
    reply_count INTEGER NOT NULL DEFAULT 0,
    last_active_text TEXT NOT NULL DEFAULT '',
    published_text TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    raw_json TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    seen_count INTEGER NOT NULL DEFAULT 1,
    UNIQUE(source_key, external_id)
);

CREATE TABLE IF NOT EXISTS evaluation_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key TEXT NOT NULL,
    external_id TEXT NOT NULL,
    rule_key TEXT NOT NULL,
    matched INTEGER NOT NULL,
    priority TEXT NOT NULL,
    reason TEXT NOT NULL,
    matched_keywords_json TEXT NOT NULL,
    excluded_keywords_json TEXT NOT NULL,
    used_price_amount REAL,
    used_spec_grams INTEGER,
    evaluated_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(source_key, external_id, rule_key)
);

CREATE TABLE IF NOT EXISTS source_item_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key TEXT NOT NULL,
    external_id TEXT NOT NULL,
    status TEXT NOT NULL,
    body_text TEXT NOT NULL DEFAULT '',
    image_urls_json TEXT NOT NULL DEFAULT '[]',
    fetched_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(source_key, external_id)
);

CREATE TABLE IF NOT EXISTS notification_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key TEXT NOT NULL,
    external_id TEXT NOT NULL,
    rule_key TEXT NOT NULL,
    channel TEXT NOT NULL,
    target TEXT NOT NULL,
    status TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    link_url TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_health (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    last_attempt_at TEXT NOT NULL,
    last_success_at TEXT,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    fetched_items INTEGER NOT NULL DEFAULT 0,
    inserted_items INTEGER NOT NULL DEFAULT 0,
    updated_items INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    backoff_until TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_controls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key TEXT NOT NULL UNIQUE,
    paused INTEGER NOT NULL DEFAULT 0,
    reason TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS item_mutes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key TEXT NOT NULL,
    external_id TEXT NOT NULL,
    muted INTEGER NOT NULL DEFAULT 1,
    reason TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(source_key, external_id)
);

CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key TEXT NOT NULL,
    status TEXT NOT NULL,
    requested_items INTEGER NOT NULL DEFAULT 0,
    fetched_items INTEGER NOT NULL DEFAULT 0,
    inserted_items INTEGER NOT NULL DEFAULT 0,
    updated_items INTEGER NOT NULL DEFAULT 0,
    matched_items INTEGER NOT NULL DEFAULT 0,
    notifications_sent INTEGER NOT NULL DEFAULT 0,
    notifications_failed INTEGER NOT NULL DEFAULT 0,
    skipped_reason TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS config_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_key TEXT NOT NULL,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    file_name TEXT,
    before_json TEXT,
    after_json TEXT,
    created_at TEXT NOT NULL
);
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_window(limit: int, offset: int, *, max_limit: int = 200) -> tuple[int, int]:
    safe_limit = max(1, min(limit, max_limit))
    safe_offset = max(0, offset)
    return safe_limit, safe_offset


class SourceItemRepository:
    def __init__(self, db_path: Path | None = None) -> None:
        settings = get_settings()
        self.db_path = db_path or settings.sqlite_db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _init_db(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA_SQL)
            self._ensure_column(connection, "source_health", "backoff_until", "TEXT")

    @staticmethod
    def _ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
        existing = {row[1] for row in rows}
        if column not in existing:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    @staticmethod
    def _is_material_change(existing: sqlite3.Row, item: SourceItem) -> bool:
        if (existing["title"] or "") != item.title:
            return True
        if (existing["summary"] or "") != item.summary:
            return True
        if (existing["published_text"] or "") != item.published_text:
            return True
        previous_replies = int(existing["reply_count"] or 0)
        if item.reply_count > previous_replies and (item.reply_count - previous_replies) >= 5:
            return True
        if (existing["last_active_text"] or "") != item.last_active_text and item.reply_count > previous_replies:
            return True
        return False

    def upsert_items(self, source_key: str, source_label: str | None, items: list[SourceItem], requested_items: int) -> SyncResponse:
        inserted = 0
        updated = 0
        reevaluate_item_ids: list[str] = []
        inserted_item_ids: list[str] = []
        now = _utc_now()

        with self.connect() as connection:
            for item in items:
                payload = item.model_dump()
                existing = connection.execute(
                    "SELECT id, title, url, reply_count, last_active_text, published_text, summary, seen_count "
                    "FROM source_items WHERE source_key = ? AND external_id = ?",
                    (item.source_key, item.external_id),
                ).fetchone()

                if existing is None:
                    connection.execute(
                        """
                        INSERT INTO source_items (
                            source_key, external_id, source_type, title, url,
                            author_name, author_url, reply_count, last_active_text,
                            published_text, summary, raw_json, first_seen_at, last_seen_at, seen_count
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            item.source_key,
                            item.external_id,
                            item.source_type,
                            item.title,
                            item.url,
                            item.author_name,
                            item.author_url,
                            item.reply_count,
                            item.last_active_text,
                            item.published_text,
                            item.summary,
                            json.dumps(payload, ensure_ascii=False),
                            now,
                            now,
                            1,
                        ),
                    )
                    inserted += 1
                    inserted_item_ids.append(item.external_id)
                    continue

                needs_reevaluation = self._is_material_change(existing, item)
                connection.execute(
                    """
                    UPDATE source_items
                    SET source_type = ?,
                        title = ?,
                        url = ?,
                        author_name = ?,
                        author_url = ?,
                        reply_count = ?,
                        last_active_text = ?,
                        published_text = ?,
                        summary = ?,
                        raw_json = ?,
                        last_seen_at = ?,
                        seen_count = seen_count + 1
                    WHERE source_key = ? AND external_id = ?
                    """,
                    (
                        item.source_type,
                        item.title,
                        item.url,
                        item.author_name,
                        item.author_url,
                        item.reply_count,
                        item.last_active_text,
                        item.published_text,
                        item.summary,
                        json.dumps(payload, ensure_ascii=False),
                        now,
                        item.source_key,
                        item.external_id,
                    ),
                )
                updated += 1
                if needs_reevaluation:
                    reevaluate_item_ids.append(item.external_id)

        return SyncResponse(
            source_key=source_key,
            source_label=source_label,
            requested_items=requested_items,
            fetched_items=len(items),
            inserted=inserted,
            updated=updated,
            reevaluated_existing=len(reevaluate_item_ids),
            inserted_item_ids=inserted_item_ids,
            reevaluate_item_ids=reevaluate_item_ids,
            items=items,
        )

    def get_item(self, source_key: str, external_id: str) -> StoredItem | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT source_key, external_id, source_type, title, url, author_name, author_url, "
                "reply_count, last_active_text, published_text, summary, first_seen_at, last_seen_at, seen_count "
                "FROM source_items WHERE source_key = ? AND external_id = ?",
                (source_key, external_id),
            ).fetchone()
        return StoredItem.model_validate(dict(row)) if row else None

    def list_items_page(self, *, source_key: str | None = None, offset: int = 0, limit: int = 20) -> tuple[list[StoredItem], int]:
        safe_limit, safe_offset = _normalize_window(limit, offset, max_limit=200)
        base_sql = (
            "SELECT source_key, external_id, source_type, title, url, author_name, author_url, "
            "reply_count, last_active_text, published_text, summary, first_seen_at, last_seen_at, seen_count "
            "FROM source_items"
        )
        count_sql = "SELECT COUNT(*) FROM source_items"
        params: list[object] = []
        if source_key:
            base_sql += " WHERE source_key = ?"
            count_sql += " WHERE source_key = ?"
            params.append(source_key)
        base_sql += " ORDER BY last_seen_at DESC LIMIT ? OFFSET ?"

        with self.connect() as connection:
            total = connection.execute(count_sql, params).fetchone()[0]
            rows = connection.execute(base_sql, [*params, safe_limit, safe_offset]).fetchall()
        return [StoredItem.model_validate(dict(row)) for row in rows], int(total)

    def list_items(self, *, source_key: str | None = None, limit: int = 20) -> list[StoredItem]:
        items, _ = self.list_items_page(source_key=source_key, offset=0, limit=limit)
        return items

    def write_evaluation_records(self, item: SourceItem, evaluation: EvaluationResponse) -> int:
        now = _utc_now()
        written = 0
        with self.connect() as connection:
            for match in evaluation.matches:
                existing = connection.execute(
                    "SELECT id FROM evaluation_records WHERE source_key = ? AND external_id = ? AND rule_key = ?",
                    (item.source_key, item.external_id, match.rule_key),
                ).fetchone()

                payload = (
                    item.source_key,
                    item.external_id,
                    match.rule_key,
                    1 if match.matched else 0,
                    match.priority,
                    match.reason,
                    json.dumps(match.matched_keywords, ensure_ascii=False),
                    json.dumps(match.excluded_keywords, ensure_ascii=False),
                    match.used_price.amount_cny if match.used_price else None,
                    match.used_spec.total_grams if match.used_spec else None,
                    now,
                )

                if existing is None:
                    connection.execute(
                        """
                        INSERT INTO evaluation_records (
                            source_key, external_id, rule_key, matched, priority, reason,
                            matched_keywords_json, excluded_keywords_json,
                            used_price_amount, used_spec_grams, evaluated_at, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        payload + (now, now),
                    )
                else:
                    connection.execute(
                        """
                        UPDATE evaluation_records
                        SET matched = ?,
                            priority = ?,
                            reason = ?,
                            matched_keywords_json = ?,
                            excluded_keywords_json = ?,
                            used_price_amount = ?,
                            used_spec_grams = ?,
                            evaluated_at = ?,
                            updated_at = ?
                        WHERE source_key = ? AND external_id = ? AND rule_key = ?
                        """,
                        (
                            1 if match.matched else 0,
                            match.priority,
                            match.reason,
                            json.dumps(match.matched_keywords, ensure_ascii=False),
                            json.dumps(match.excluded_keywords, ensure_ascii=False),
                            match.used_price.amount_cny if match.used_price else None,
                            match.used_spec.total_grams if match.used_spec else None,
                            now,
                            now,
                            item.source_key,
                            item.external_id,
                            match.rule_key,
                        ),
                    )
                written += 1
        return written

    def upsert_detail(self, detail: SourceItemDetail) -> None:
        now = _utc_now()
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT id FROM source_item_details WHERE source_key = ? AND external_id = ?",
                (detail.source_key, detail.external_id),
            ).fetchone()
            image_urls_json = json.dumps(detail.image_urls, ensure_ascii=False)
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO source_item_details (
                        source_key, external_id, status, body_text, image_urls_json, fetched_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        detail.source_key,
                        detail.external_id,
                        detail.status,
                        detail.body_text,
                        image_urls_json,
                        detail.fetched_at,
                        now,
                        now,
                    ),
                )
            else:
                connection.execute(
                    """
                    UPDATE source_item_details
                    SET status = ?,
                        body_text = ?,
                        image_urls_json = ?,
                        fetched_at = ?,
                        updated_at = ?
                    WHERE source_key = ? AND external_id = ?
                    """,
                    (
                        detail.status,
                        detail.body_text,
                        image_urls_json,
                        detail.fetched_at,
                        now,
                        detail.source_key,
                        detail.external_id,
                    ),
                )

    def get_detail(self, source_key: str, external_id: str) -> SourceItemDetail | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT source_key, external_id, status, body_text, image_urls_json, fetched_at
                FROM source_item_details
                WHERE source_key = ? AND external_id = ?
                """,
                (source_key, external_id),
            ).fetchone()
        if row is None:
            return None
        payload = dict(row)
        payload["image_urls"] = json.loads(payload.pop("image_urls_json"))
        return SourceItemDetail.model_validate(payload)

    def list_evaluation_records(self, *, source_key: str | None = None, matched_only: bool = False, limit: int = 50) -> list[StoredEvaluationRecord]:
        items, _ = self.list_evaluation_records_page(source_key=source_key, matched_only=matched_only, offset=0, limit=limit)
        return items

    def list_evaluation_records_page(
        self,
        *,
        source_key: str | None = None,
        matched_only: bool = False,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[StoredEvaluationRecord], int]:
        safe_limit, safe_offset = _normalize_window(limit, offset, max_limit=200)
        sql = (
            "SELECT source_key, external_id, rule_key, matched, priority, reason, "
            "matched_keywords_json, excluded_keywords_json, used_price_amount, used_spec_grams, "
            "evaluated_at, created_at, updated_at FROM evaluation_records"
        )
        count_sql = "SELECT COUNT(*) FROM evaluation_records"
        params: list[object] = []
        filters: list[str] = []

        if source_key:
            filters.append("source_key = ?")
            params.append(source_key)
        if matched_only:
            filters.append("matched = 1")

        if filters:
            where = " WHERE " + " AND ".join(filters)
            sql += where
            count_sql += where
        sql += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"

        with self.connect() as connection:
            total = connection.execute(count_sql, params).fetchone()[0]
            rows = connection.execute(sql, [*params, safe_limit, safe_offset]).fetchall()

        items: list[StoredEvaluationRecord] = []
        for row in rows:
            payload = dict(row)
            payload["matched"] = bool(payload["matched"])
            payload["matched_keywords"] = json.loads(payload.pop("matched_keywords_json"))
            payload["excluded_keywords"] = json.loads(payload.pop("excluded_keywords_json"))
            items.append(StoredEvaluationRecord.model_validate(payload))
        return items, int(total)

    def write_notification_record(
        self,
        *,
        source_key: str,
        external_id: str,
        rule_key: str,
        channel: str,
        target: str,
        status: str,
        title: str,
        content: str,
        link_url: str | None,
        error_message: str | None,
    ) -> None:
        now = _utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO notification_records (
                    source_key, external_id, rule_key, channel, target, status, title,
                    content, link_url, error_message, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_key,
                    external_id,
                    rule_key,
                    channel,
                    target,
                    status,
                    title,
                    content,
                    link_url,
                    error_message,
                    now,
                    now,
                ),
            )

    def get_recent_sent_notification(
        self,
        *,
        source_key: str,
        external_id: str,
        rule_key: str,
        target: str,
        since_iso: str,
    ) -> NotificationRecord | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT source_key, external_id, rule_key, channel, target, status, title, content,
                       link_url, created_at, updated_at, error_message
                FROM notification_records
                WHERE source_key = ?
                  AND external_id = ?
                  AND rule_key = ?
                  AND target = ?
                  AND status = 'sent'
                  AND updated_at >= ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (source_key, external_id, rule_key, target, since_iso),
            ).fetchone()
        return NotificationRecord.model_validate(dict(row)) if row else None

    def list_notification_records(self, *, source_key: str | None = None, rule_key: str | None = None, limit: int = 50) -> list[NotificationRecord]:
        items, _ = self.list_notification_records_page(source_key=source_key, rule_key=rule_key, offset=0, limit=limit)
        return items

    def list_notification_records_page(
        self,
        *,
        source_key: str | None = None,
        rule_key: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[NotificationRecord], int]:
        safe_limit, safe_offset = _normalize_window(limit, offset, max_limit=200)
        sql = (
            "SELECT source_key, external_id, rule_key, channel, target, status, title, content, "
            "link_url, created_at, updated_at, error_message FROM notification_records"
        )
        count_sql = "SELECT COUNT(*) FROM notification_records"
        params: list[object] = []
        filters: list[str] = []
        if source_key:
            filters.append("source_key = ?")
            params.append(source_key)
        if rule_key:
            filters.append("rule_key = ?")
            params.append(rule_key)
        if filters:
            where = " WHERE " + " AND ".join(filters)
            sql += where
            count_sql += where
        sql += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"

        with self.connect() as connection:
            total = connection.execute(count_sql, params).fetchone()[0]
            rows = connection.execute(sql, [*params, safe_limit, safe_offset]).fetchall()
        return [NotificationRecord.model_validate(dict(row)) for row in rows], int(total)

    def list_matched_items(
        self,
        *,
        source_key: str | None = None,
        rule_key: str | None = None,
        exclude_muted: bool = True,
        limit: int = 50,
    ) -> list[MatchedItemRecord]:
        items, _ = self.list_matched_items_page(
            source_key=source_key,
            rule_key=rule_key,
            exclude_muted=exclude_muted,
            offset=0,
            limit=limit,
        )
        return items

    def list_matched_items_page(
        self,
        *,
        source_key: str | None = None,
        rule_key: str | None = None,
        exclude_muted: bool = True,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[MatchedItemRecord], int]:
        safe_limit, safe_offset = _normalize_window(limit, offset, max_limit=200)
        sql = (
            "SELECT e.source_key, e.external_id, s.source_type, e.rule_key, s.title, s.url, "
            "e.matched, e.reason, e.used_price_amount, e.used_spec_grams, e.evaluated_at, "
            "s.last_seen_at, s.seen_count "
            "FROM evaluation_records e "
            "JOIN source_items s ON s.source_key = e.source_key AND s.external_id = e.external_id "
            "WHERE e.matched = 1"
        )
        count_sql = (
            "SELECT COUNT(*) "
            "FROM evaluation_records e "
            "JOIN source_items s ON s.source_key = e.source_key AND s.external_id = e.external_id "
            "WHERE e.matched = 1"
        )
        params: list[object] = []
        if source_key:
            sql += " AND e.source_key = ?"
            count_sql += " AND e.source_key = ?"
            params.append(source_key)
        if rule_key:
            sql += " AND e.rule_key = ?"
            count_sql += " AND e.rule_key = ?"
            params.append(rule_key)
        if exclude_muted:
            clause = (
                " AND NOT EXISTS ("
                "SELECT 1 FROM item_mutes m "
                "WHERE m.source_key = e.source_key AND m.external_id = e.external_id AND m.muted = 1)"
            )
            sql += clause
            count_sql += clause
        sql += " ORDER BY e.updated_at DESC LIMIT ? OFFSET ?"

        with self.connect() as connection:
            total = connection.execute(count_sql, params).fetchone()[0]
            rows = connection.execute(sql, [*params, safe_limit, safe_offset]).fetchall()
        return [MatchedItemRecord.model_validate(dict(row)) for row in rows], int(total)

    def mark_source_success(
        self,
        *,
        source_key: str,
        fetched_items: int,
        inserted_items: int,
        updated_items: int,
    ) -> None:
        now = _utc_now()
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT id FROM source_health WHERE source_key = ?",
                (source_key,),
            ).fetchone()
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO source_health (
                        source_key, status, last_attempt_at, last_success_at, consecutive_failures,
                        fetched_items, inserted_items, updated_items, last_error, backoff_until, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (source_key, "ok", now, now, 0, fetched_items, inserted_items, updated_items, None, None, now),
                )
            else:
                connection.execute(
                    """
                    UPDATE source_health
                    SET status = ?,
                        last_attempt_at = ?,
                        last_success_at = ?,
                        consecutive_failures = 0,
                        fetched_items = ?,
                        inserted_items = ?,
                        updated_items = ?,
                        last_error = NULL,
                        backoff_until = NULL,
                        updated_at = ?
                    WHERE source_key = ?
                    """,
                    ("ok", now, now, fetched_items, inserted_items, updated_items, now, source_key),
                )

    def mark_source_failure(self, *, source_key: str, error_message: str, base_interval_minutes: int | None = None) -> None:
        now = _utc_now()
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT consecutive_failures, last_success_at FROM source_health WHERE source_key = ?",
                (source_key,),
            ).fetchone()
            previous_failures = int(existing["consecutive_failures"] or 0) if existing else 0
            current_failures = previous_failures + 1
            backoff_until = None
            if current_failures >= 3:
                base = base_interval_minutes or 10
                backoff_minutes = min(base * current_failures, 60)
                backoff_until = (datetime.now(timezone.utc) + timedelta(minutes=backoff_minutes)).isoformat()
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO source_health (
                        source_key, status, last_attempt_at, last_success_at, consecutive_failures,
                        fetched_items, inserted_items, updated_items, last_error, backoff_until, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_key,
                        "backoff" if backoff_until else "error",
                        now,
                        None,
                        current_failures,
                        0,
                        0,
                        0,
                        error_message,
                        backoff_until,
                        now,
                    ),
                )
            else:
                connection.execute(
                    """
                    UPDATE source_health
                    SET status = ?,
                        last_attempt_at = ?,
                        consecutive_failures = ?,
                        last_error = ?,
                        backoff_until = ?,
                        updated_at = ?
                    WHERE source_key = ?
                    """,
                    ("backoff" if backoff_until else "error", now, current_failures, error_message, backoff_until, now, source_key),
                )

    def list_source_health(self, *, source_key: str | None = None, limit: int = 50) -> list[SourceHealthRecord]:
        items, _ = self.list_source_health_page(source_key=source_key, offset=0, limit=limit)
        return items

    def list_source_health_page(self, *, source_key: str | None = None, offset: int = 0, limit: int = 50) -> tuple[list[SourceHealthRecord], int]:
        safe_limit, safe_offset = _normalize_window(limit, offset, max_limit=200)
        sql = (
            "SELECT h.source_key, h.status, h.last_attempt_at, h.last_success_at, h.consecutive_failures, "
            "h.fetched_items, h.inserted_items, h.updated_items, h.last_error, "
            "COALESCE(c.paused, 0) AS paused, c.reason AS pause_reason, h.backoff_until, h.updated_at "
            "FROM source_health h "
            "LEFT JOIN source_controls c ON c.source_key = h.source_key"
        )
        count_sql = "SELECT COUNT(*) FROM source_health h"
        params: list[object] = []
        if source_key:
            sql += " WHERE h.source_key = ?"
            count_sql += " WHERE h.source_key = ?"
            params.append(source_key)
        sql += " ORDER BY h.updated_at DESC LIMIT ? OFFSET ?"

        with self.connect() as connection:
            total = connection.execute(count_sql, params).fetchone()[0]
            rows = connection.execute(sql, [*params, safe_limit, safe_offset]).fetchall()
        items = []
        for row in rows:
            payload = dict(row)
            payload["paused"] = bool(payload["paused"])
            items.append(SourceHealthRecord.model_validate(payload))
        return items, int(total)

    def set_source_paused(self, *, source_key: str, paused: bool, reason: str | None = None) -> SourceControlRecord:
        now = _utc_now()
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT id FROM source_controls WHERE source_key = ?",
                (source_key,),
            ).fetchone()
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO source_controls (source_key, paused, reason, updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (source_key, 1 if paused else 0, reason, now),
                )
            else:
                connection.execute(
                    """
                    UPDATE source_controls
                    SET paused = ?, reason = ?, updated_at = ?
                    WHERE source_key = ?
                    """,
                    (1 if paused else 0, reason, now, source_key),
                )
        return SourceControlRecord(source_key=source_key, paused=paused, reason=reason, updated_at=now)

    def get_source_control(self, source_key: str) -> SourceControlRecord | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT source_key, paused, reason, updated_at FROM source_controls WHERE source_key = ?",
                (source_key,),
            ).fetchone()
        if row is None:
            return None
        payload = dict(row)
        payload["paused"] = bool(payload["paused"])
        return SourceControlRecord.model_validate(payload)

    def list_source_controls(self, limit: int = 100) -> list[SourceControlRecord]:
        items, _ = self.list_source_controls_page(offset=0, limit=limit)
        return items

    def list_source_controls_page(self, offset: int = 0, limit: int = 100) -> tuple[list[SourceControlRecord], int]:
        safe_limit, safe_offset = _normalize_window(limit, offset, max_limit=200)
        with self.connect() as connection:
            total = connection.execute("SELECT COUNT(*) FROM source_controls").fetchone()[0]
            rows = connection.execute(
                "SELECT source_key, paused, reason, updated_at FROM source_controls ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (safe_limit, safe_offset),
            ).fetchall()
        items = []
        for row in rows:
            payload = dict(row)
            payload["paused"] = bool(payload["paused"])
            items.append(SourceControlRecord.model_validate(payload))
        return items, int(total)

    def set_item_muted(self, *, source_key: str, external_id: str, muted: bool, reason: str | None = None) -> ItemMuteRecord:
        now = _utc_now()
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT id FROM item_mutes WHERE source_key = ? AND external_id = ?",
                (source_key, external_id),
            ).fetchone()
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO item_mutes (source_key, external_id, muted, reason, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (source_key, external_id, 1 if muted else 0, reason, now),
                )
            else:
                connection.execute(
                    """
                    UPDATE item_mutes
                    SET muted = ?, reason = ?, updated_at = ?
                    WHERE source_key = ? AND external_id = ?
                    """,
                    (1 if muted else 0, reason, now, source_key, external_id),
                )
        return ItemMuteRecord(source_key=source_key, external_id=external_id, muted=muted, reason=reason, updated_at=now)

    def is_item_muted(self, *, source_key: str, external_id: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT muted FROM item_mutes WHERE source_key = ? AND external_id = ?",
                (source_key, external_id),
            ).fetchone()
        return bool(row["muted"]) if row else False

    def list_item_mutes(self, source_key: str | None = None, limit: int = 100) -> list[ItemMuteRecord]:
        items, _ = self.list_item_mutes_page(source_key=source_key, offset=0, limit=limit)
        return items

    def list_item_mutes_page(self, source_key: str | None = None, offset: int = 0, limit: int = 100) -> tuple[list[ItemMuteRecord], int]:
        safe_limit, safe_offset = _normalize_window(limit, offset, max_limit=200)
        sql = "SELECT source_key, external_id, muted, reason, updated_at FROM item_mutes"
        count_sql = "SELECT COUNT(*) FROM item_mutes"
        params: list[object] = []
        if source_key:
            sql += " WHERE source_key = ?"
            count_sql += " WHERE source_key = ?"
            params.append(source_key)
        sql += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        with self.connect() as connection:
            total = connection.execute(count_sql, params).fetchone()[0]
            rows = connection.execute(sql, [*params, safe_limit, safe_offset]).fetchall()
        items = []
        for row in rows:
            payload = dict(row)
            payload["muted"] = bool(payload["muted"])
            items.append(ItemMuteRecord.model_validate(payload))
        return items, int(total)

    def get_item_bundle(self, source_key: str, external_id: str) -> dict[str, object] | None:
        item = self.get_item(source_key, external_id)
        if item is None:
            return None
        detail = self.get_detail(source_key, external_id)
        evaluations = [
            record.model_dump()
            for record in self.list_evaluation_records(limit=200)
            if record.source_key == source_key and record.external_id == external_id
        ]
        notifications = [
            record.model_dump()
            for record in self.list_notification_records(limit=200)
            if record.source_key == source_key and record.external_id == external_id
        ]
        muted = next(
            (record for record in self.list_item_mutes(limit=200) if record.source_key == source_key and record.external_id == external_id),
            None,
        )
        return {
            "item": item.model_dump(),
            "detail": detail.model_dump() if detail else None,
            "evaluations": evaluations,
            "notifications": notifications,
            "muted": muted.model_dump() if muted else None,
        }

    def write_sync_run(
        self,
        *,
        source_key: str,
        status: str,
        requested_items: int,
        fetched_items: int,
        inserted_items: int,
        updated_items: int,
        matched_items: int,
        notifications_sent: int,
        notifications_failed: int,
        skipped_reason: str | None = None,
        error_message: str | None = None,
    ) -> None:
        now = _utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO sync_runs (
                    source_key, status, requested_items, fetched_items, inserted_items, updated_items,
                    matched_items, notifications_sent, notifications_failed, skipped_reason, error_message, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_key,
                    status,
                    requested_items,
                    fetched_items,
                    inserted_items,
                    updated_items,
                    matched_items,
                    notifications_sent,
                    notifications_failed,
                    skipped_reason,
                    error_message,
                    now,
                ),
            )

    def summarize_last_24h(self) -> SyncStats24h:
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS sync_runs,
                       COALESCE(SUM(inserted_items), 0) AS inserted_items,
                       COALESCE(SUM(updated_items), 0) AS updated_items,
                       COALESCE(SUM(matched_items), 0) AS matched_items,
                       COALESCE(SUM(notifications_sent), 0) AS notifications_sent,
                       COALESCE(SUM(notifications_failed), 0) AS notifications_failed,
                       COALESCE(SUM(CASE WHEN status IN ('error', 'backoff') THEN 1 ELSE 0 END), 0) AS source_errors
                FROM sync_runs
                WHERE created_at >= ?
                """,
                (since,),
            ).fetchone()
        return SyncStats24h.model_validate(dict(row))

    def write_config_audit(
        self,
        *,
        entity_type: str,
        entity_key: str,
        action: str,
        actor: str,
        file_name: str | None,
        before_payload: dict | None,
        after_payload: dict | None,
    ) -> None:
        now = _utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO config_audit (
                    entity_type, entity_key, action, actor, file_name, before_json, after_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entity_type,
                    entity_key,
                    action,
                    actor,
                    file_name,
                    json.dumps(before_payload, ensure_ascii=False) if before_payload is not None else None,
                    json.dumps(after_payload, ensure_ascii=False) if after_payload is not None else None,
                    now,
                ),
            )

    def list_config_audit(self, *, entity_type: str | None = None, offset: int = 0, limit: int = 50) -> tuple[list[ConfigAuditRecord], int]:
        safe_limit, safe_offset = _normalize_window(limit, offset, max_limit=200)
        sql = "SELECT entity_type, entity_key, action, actor, file_name, before_json, after_json, created_at FROM config_audit"
        count_sql = "SELECT COUNT(*) FROM config_audit"
        params: list[object] = []
        if entity_type:
            sql += " WHERE entity_type = ?"
            count_sql += " WHERE entity_type = ?"
            params.append(entity_type)
        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        with self.connect() as connection:
            total = connection.execute(count_sql, params).fetchone()[0]
            rows = connection.execute(sql, [*params, safe_limit, safe_offset]).fetchall()
        items: list[ConfigAuditRecord] = []
        for row in rows:
            payload = dict(row)
            payload["before_payload"] = json.loads(payload.pop("before_json")) if payload.get("before_json") else None
            payload["after_payload"] = json.loads(payload.pop("after_json")) if payload.get("after_json") else None
            items.append(ConfigAuditRecord.model_validate(payload))
        return items, int(total)

    def count_source_items(self, source_key: str) -> int:
        with self.connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM source_items WHERE source_key = ?", (source_key,)).fetchone()[0])

    def rule_history_counts(self, rule_key: str) -> dict[str, int]:
        with self.connect() as connection:
            eval_count = int(connection.execute("SELECT COUNT(*) FROM evaluation_records WHERE rule_key = ?", (rule_key,)).fetchone()[0])
            notification_count = int(connection.execute("SELECT COUNT(*) FROM notification_records WHERE rule_key = ?", (rule_key,)).fetchone()[0])
        return {
            "evaluation_records": eval_count,
            "notification_records": notification_count,
        }
