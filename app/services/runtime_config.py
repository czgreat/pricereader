from __future__ import annotations

from pathlib import Path

from app.core.settings import get_settings
from app.models.runtime_config import RuntimeConfigPayload, RuntimeConfigViewPayload


MANAGED_KEYS = (
    "WECHAT_PUSH_URL",
    "DOUBAN_COOKIE",
    "SMZDM_COOKIE",
    "WECHAT_PUSH_TOKEN",
    "WECHAT_TARGET_ID",
)

SENSITIVE_KEYS = {
    "DOUBAN_COOKIE",
    "SMZDM_COOKIE",
    "WECHAT_PUSH_TOKEN",
    "WECHAT_TARGET_ID",
}


def _mask_value(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "••••••••"
    return f"{value[:2]}••••••{value[-2:]}"


class RuntimeConfigStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or get_settings().local_env_path

    def load(self) -> RuntimeConfigPayload:
        values = self._read_env_file()
        settings = get_settings()
        return RuntimeConfigPayload(
            wechat_push_url=values.get("WECHAT_PUSH_URL", settings.wechat_push_url),
            douban_cookie=values.get("DOUBAN_COOKIE", settings.douban_cookie),
            smzdm_cookie=values.get("SMZDM_COOKIE", settings.smzdm_cookie),
            wechat_push_token=values.get("WECHAT_PUSH_TOKEN", settings.wechat_push_token),
            wechat_target_id=values.get("WECHAT_TARGET_ID", settings.wechat_target_id),
        )

    def load_view(self, *, reveal: bool = False) -> RuntimeConfigViewPayload:
        payload = self.load()
        configured = {
            "wechat_push_url": bool(payload.wechat_push_url),
            "douban_cookie": bool(payload.douban_cookie),
            "smzdm_cookie": bool(payload.smzdm_cookie),
            "wechat_push_token": bool(payload.wechat_push_token),
            "wechat_target_id": bool(payload.wechat_target_id),
        }
        if reveal:
            return RuntimeConfigViewPayload(values=payload, configured=configured, revealed=True)

        masked = payload.model_copy(
            update={
                "douban_cookie": _mask_value(payload.douban_cookie),
                "smzdm_cookie": _mask_value(payload.smzdm_cookie),
                "wechat_push_token": _mask_value(payload.wechat_push_token),
                "wechat_target_id": _mask_value(payload.wechat_target_id),
            }
        )
        return RuntimeConfigViewPayload(values=masked, configured=configured, revealed=False)

    def save(self, payload: RuntimeConfigPayload) -> RuntimeConfigPayload:
        values = self._read_env_file()
        values["WECHAT_PUSH_URL"] = payload.wechat_push_url.strip()
        values["DOUBAN_COOKIE"] = payload.douban_cookie.strip()
        values["SMZDM_COOKIE"] = payload.smzdm_cookie.strip()
        values["WECHAT_PUSH_TOKEN"] = payload.wechat_push_token.strip()
        values["WECHAT_TARGET_ID"] = payload.wechat_target_id.strip()
        self._write_env_file(values)
        get_settings.cache_clear()
        return self.load()

    def _read_env_file(self) -> dict[str, str]:
        if not self.path.exists():
            return {}

        values: dict[str, str] = {}
        for line in self.path.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            values[key.strip()] = value
        return values

    def _write_env_file(self, values: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Local runtime config for PriceReader",
            "# This file is intentionally not tracked by git.",
        ]
        for key in MANAGED_KEYS:
            lines.append(f"{key}={values.get(key, '')}")
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
