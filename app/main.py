from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.dashboard_page import DASHBOARD_PAGE_PATH
from app.api.routes import router as api_router
from app.core.settings import get_settings
from app.services.config_loader import load_config_snapshot
from app.tasks.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    settings.ensure_runtime_dirs()
    load_config_snapshot()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="PriceReader", version=get_settings().app_version, lifespan=lifespan)
app.include_router(api_router)
app.mount("/static", StaticFiles(directory=Path(__file__).resolve().parent / "static"), name="static")


@app.get("/", include_in_schema=False)
@app.get("/ui", include_in_schema=False)
def ui_dashboard() -> FileResponse:
    return FileResponse(DASHBOARD_PAGE_PATH)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "project": settings.project_name,
        "version": settings.app_version,
    }
