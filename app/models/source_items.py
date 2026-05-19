from __future__ import annotations

from pydantic import BaseModel


class SourceItem(BaseModel):
    source_key: str
    external_id: str
    title: str
    url: str
    source_type: str
    author_name: str | None = None
    author_url: str | None = None
    reply_count: int = 0
    last_active_text: str = ""
    published_text: str = ""
    summary: str = ""


class SourceFetchResponse(BaseModel):
    source_key: str
    source_label: str | None = None
    requested_items: int
    returned_items: int
    items: list[SourceItem]


class SyncResponse(BaseModel):
    source_key: str
    source_label: str | None = None
    requested_items: int
    fetched_items: int
    inserted: int
    updated: int
    reevaluated_existing: int = 0
    inserted_item_ids: list[str] = []
    reevaluate_item_ids: list[str] = []
    items: list[SourceItem]


class StoredItem(BaseModel):
    source_key: str
    external_id: str
    source_type: str
    title: str
    url: str
    author_name: str | None = None
    author_url: str | None = None
    reply_count: int = 0
    last_active_text: str = ""
    published_text: str = ""
    summary: str = ""
    first_seen_at: str
    last_seen_at: str
    seen_count: int


class SourceItemDetail(BaseModel):
    source_key: str
    external_id: str
    status: str
    body_text: str = ""
    image_urls: list[str] = []
    fetched_at: str
