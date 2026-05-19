from __future__ import annotations

from pydantic import BaseModel


class SourceControlRecord(BaseModel):
    source_key: str
    paused: bool
    reason: str | None = None
    updated_at: str


class ItemMuteRecord(BaseModel):
    source_key: str
    external_id: str
    muted: bool
    reason: str | None = None
    updated_at: str


class SourceControlUpdate(BaseModel):
    reason: str | None = None


class ItemMuteUpdate(BaseModel):
    reason: str | None = None

