from fastapi.testclient import TestClient

from app.main import app


def test_summary_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["config"]["source_count"] >= 5
    assert payload["config"]["rule_count"] >= 2


def test_summary_uses_runtime_config_for_integrations(monkeypatch) -> None:
    from app.api import routes as routes_module
    from app.models.runtime_config import RuntimeConfigPayload

    class FakeRuntimeStore:
        def load(self) -> RuntimeConfigPayload:
            return RuntimeConfigPayload(
                wechat_push_url="http://localhost:23456/api/push",
                wechat_push_token="token",
                wechat_target_id="target",
                douban_cookie="ck=1",
                smzdm_cookie="smzdm=1",
            )

    monkeypatch.setattr(routes_module, "RuntimeConfigStore", FakeRuntimeStore)

    with TestClient(app) as client:
        response = client.get("/api/v1/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["integrations"]["wechat_configured"] is True
    assert payload["integrations"]["douban_cookie_configured"] is True
    assert payload["integrations"]["smzdm_cookie_configured"] is True


def test_ui_bootstrap_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/ui/bootstrap")

    assert response.status_code == 200
    payload = response.json()
    assert "summary" in payload
    assert "runtime_config" in payload
    assert "sources" in payload
    assert "rules" in payload
    assert "stats_24h" in payload
    assert "source_health" in payload


def test_runtime_config_endpoint_is_masked_by_default() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/runtime-config")

    assert response.status_code == 200
    payload = response.json()
    assert payload["revealed"] is False
    assert "values" in payload
    assert "configured" in payload


def test_runtime_settings_page_uses_static_assets() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/settings")
        css_response = client.get("/static/settings.css")
        js_response = client.get("/static/settings.js")
        shared_runtime_response = client.get("/static/shared/runtime-config.js")

    assert response.status_code == 200
    assert css_response.status_code == 200
    assert js_response.status_code == 200
    assert shared_runtime_response.status_code == 200
    assert '/static/settings.css' in response.text
    assert 'type="module" src="/static/settings.js"' in response.text
    assert "PriceReader 运行时设置" in response.text
    assert "buildRuntimePayload" in shared_runtime_response.text


def test_stats_endpoint_available() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/stats/24h")

    assert response.status_code == 200
    payload = response.json()
    assert "sync_runs" in payload


def test_item_detail_view_not_found_returns_404() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/items/unknown/item-1/detail-view")

    assert response.status_code == 404


def test_evaluate_endpoint() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/evaluate",
            json={
                "source_key": "smzdm_keywords_primary",
                "title": "欧乐B iO3 电动牙刷 到手339元",
                "body": "整机好价，适合自用。",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    oralb = next(item for item in payload["matches"] if item["rule_key"] == "oralb_io3")
    assert oralb["matched"] is True


def test_root_opens_console() -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "PriceReader 控制台" in response.text
    assert "<title>PriceReader 控制台</title>" in response.text


def test_dashboard_page_available() -> None:
    with TestClient(app) as client:
        response = client.get("/ui")

    assert response.status_code == 200
    assert "PriceReader 控制台" in response.text
    assert '/static/dashboard.css' in response.text
    assert 'type="module" src="/static/dashboard.js"' in response.text


def test_dashboard_core_js_contains_client_safety_helpers() -> None:
    with TestClient(app) as client:
        response = client.get("/static/dashboard/core.js")

    assert response.status_code == 200
    assert "function escapeHtml" in response.text
    assert "function safeUrl" in response.text


def test_dashboard_static_css_available() -> None:
    with TestClient(app) as client:
        response = client.get("/static/dashboard.css")
        base_response = client.get("/static/dashboard/base.css")

    assert response.status_code == 200
    assert base_response.status_code == 200
    assert '@import url("/static/dashboard/base.css");' in response.text
    assert ":root {" in base_response.text
    assert "--shadow-soft:" in base_response.text


def test_dashboard_static_js_keeps_record_search_local_to_current_page() -> None:
    with TestClient(app) as client:
        page_response = client.get("/")
        records_response = client.get("/static/dashboard/records.js")
        entry_response = client.get("/static/dashboard.js")

    assert page_response.status_code == 200
    assert records_response.status_code == 200
    assert entry_response.status_code == 200
    assert "搜索当前页标题 / 来源 / 规则" in page_response.text
    assert "当前页筛后" in records_response.text
    assert "dashboard.renderRecords({ reload: false })" in records_response.text
    assert 'import "./dashboard/core.js";' in entry_response.text or 'from "./dashboard/core.js"' in entry_response.text


def test_dashboard_page_exposes_rule_management_workspace() -> None:
    with TestClient(app) as client:
        response = client.get("/")
        config_response = client.get("/static/dashboard/config-sections.js")

    assert response.status_code == 200
    assert config_response.status_code == 200
    assert "规则管理台" in response.text
    assert 'id="rule-search-input"' in response.text
    assert 'data-rule-editor-panel="basic"' in response.text
    assert 'data-rule-editor-panel="keywords"' in response.text
    assert 'data-rule-editor-panel="thresholds"' in response.text
    assert "必须包含这些词" in response.text
    assert "价格不低于（元）" in response.text
    assert "价格不高于（元）" in response.text
    assert "规格限制方式" in response.text
    assert "重复提醒间隔（小时）" in response.text
    assert 'placeholder="例如 2"' in response.text
    assert "默认 2 小时，也可以在右侧手动改" in config_response.text


def test_unknown_source_returns_404() -> None:
    with TestClient(app) as client:
        response = client.post("/api/v1/sources/not-a-real-source/sync-evaluate?max_items=3")

    assert response.status_code == 404
