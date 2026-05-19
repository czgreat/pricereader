from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("deploy/fnos/.env", ".env", "data/runtime/.env.local", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    project_name: str = "pricereader"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000

    data_root: Path = Path("data")
    sqlite_dir: Path = Path("data/sqlite")
    sqlite_db_name: str = "pricereader.db"
    media_dir: Path = Path("data/media")
    runtime_dir: Path = Path("data/runtime")
    logs_dir: Path = Path("logs")
    config_root: Path = Path("config")
    sources_dir: Path = Path("config/sources")
    rules_dir: Path = Path("config/rules")
    local_env_path: Path = Path("data/runtime/.env.local")

    wechat_push_url: str = "http://localhost:23456/api/push"
    wechat_push_token: str = ""
    wechat_target_id: str = ""
    smzdm_cookie: str = ""
    douban_cookie: str = ""

    def ensure_runtime_dirs(self) -> None:
        for path in (self.data_root, self.sqlite_dir, self.media_dir, self.runtime_dir, self.logs_dir):
            path.mkdir(parents=True, exist_ok=True)

    @property
    def sqlite_db_path(self) -> Path:
        return self.sqlite_dir / self.sqlite_db_name


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
