from __future__ import annotations

from pydantic import BaseModel


class RuntimeConfigPayload(BaseModel):
    wechat_push_url: str = ""
    douban_cookie: str = ""
    smzdm_cookie: str = ""
    wechat_push_token: str = ""
    wechat_target_id: str = ""


class RuntimeConfigViewPayload(BaseModel):
    values: RuntimeConfigPayload
    configured: dict[str, bool]
    revealed: bool = False
