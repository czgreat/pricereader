import { dashboard } from "./dashboard/core.js";
import "./dashboard/detail.js";
import "./dashboard/overview.js";
import "./dashboard/config-sections.js";
import "./dashboard/records.js";

const { state, qs, setAction, fetchJson } = dashboard;

dashboard.refreshAll = async function refreshAll() {
  state.bootstrap = await fetchJson("/api/v1/ui/bootstrap");
  state.runtimeView = state.bootstrap.runtime_config;
  if (!state.selectedSourceKey && state.bootstrap.sources.length) state.selectedSourceKey = state.bootstrap.sources[0].source_key;
  if (!state.selectedRuleKey && state.bootstrap.rules.length) state.selectedRuleKey = state.bootstrap.rules[0].rule_key;
  dashboard.renderOverview();
  dashboard.renderRuntimeForm();
  dashboard.renderSourceList();
  dashboard.renderSourceForm();
  dashboard.renderRuleList();
  dashboard.renderRuleForm();
  dashboard.buildRecordFilters();
  dashboard.syncSectionHeader();
  await dashboard.renderRecords();
  qs("#updated-text").textContent = `最近刷新 ${new Date().toLocaleString("zh-CN", { hour12: false })}`;
  setAction("已刷新");
};

dashboard.saveRuntimeConfig = async function saveRuntimeConfig(event) {
  event.preventDefault();
  setAction("保存运行时设置...");
  const payload = await dashboard.buildRuntimeSavePayload();
  await fetchJson("/api/v1/runtime-config", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  state.runtimeView = await fetchJson("/api/v1/runtime-config?reveal=false");
  await dashboard.refreshAll();
  setAction("运行时设置已保存");
};

dashboard.reloadConfigAndScheduler = async function reloadConfigAndScheduler() {
  await fetchJson("/api/v1/config/reload", { method: "POST" });
  await dashboard.refreshAll();
  setAction("配置和调度器已重载");
};

dashboard.changePage = async function changePage(direction) {
  const page = state.paging[state.activeTab];
  const nextOffset = page.offset + direction * page.limit;
  if (nextOffset < 0) return;
  page.offset = nextOffset;
  await dashboard.renderRecords();
};

document.addEventListener("click", async (event) => {
  const tab = event.target.closest(".subtab");
  if (tab) {
    state.activeTab = tab.dataset.tab;
    state.recordDetail = null;
    state.paging[state.activeTab].offset = 0;
    await dashboard.renderRecords();
  }
  const jump = event.target.closest("[data-jump-section]");
  if (jump) {
    dashboard.switchSection(jump.dataset.jumpSection, jump.dataset.jumpTab || "");
  }
  const nav = event.target.closest("[data-section-nav]");
  if (nav) {
    dashboard.switchSection(nav.dataset.sectionNav, nav.dataset.tabTarget || "");
  }
  const rulePanel = event.target.closest("[data-rule-editor-panel]");
  if (rulePanel && rulePanel.classList.contains("editor-tab")) {
    dashboard.switchRulePanel(rulePanel.dataset.ruleEditorPanel);
  }
});

qs("#refresh-button").addEventListener("click", dashboard.refreshAll);
qs("#reload-config-button").addEventListener("click", dashboard.reloadConfigAndScheduler);
qs("#runtime-form").addEventListener("submit", (event) => dashboard.saveRuntimeConfig(event).catch((error) => setAction(error.message, true)));
qs("#runtime-reveal-button").addEventListener("click", () => dashboard.toggleRuntimeReveal().catch((error) => setAction(error.message, true)));
qs("#source-form").addEventListener("submit", (event) => dashboard.saveSourceConfig(event).catch((error) => setAction(error.message, true)));
qs("#source-create-button").addEventListener("click", dashboard.enterCreateSourceMode);
qs("#source-duplicate-button").addEventListener("click", () => dashboard.duplicateSource().catch((error) => setAction(error.message, true)));
qs("#source-delete-button").addEventListener("click", () => dashboard.deleteSourceConfig().catch((error) => setAction(error.message, true)));
qs("#source-toggle-button").addEventListener("click", () => dashboard.toggleSourcePause().catch((error) => setAction(error.message, true)));
qs("#source-sync-button").addEventListener("click", () => dashboard.syncSourceNow().catch((error) => setAction(error.message, true)));
qs("#rule-form").addEventListener("submit", (event) => dashboard.saveRuleConfig(event).catch((error) => setAction(error.message, true)));
qs("#rule-create-button").addEventListener("click", dashboard.enterCreateRuleMode);
qs("#rule-create-shortcut").addEventListener("click", dashboard.enterCreateRuleMode);
qs("#rule-duplicate-button").addEventListener("click", () => dashboard.duplicateRule().catch((error) => setAction(error.message, true)));
qs("#rule-delete-button").addEventListener("click", () => dashboard.deleteRuleConfig().catch((error) => setAction(error.message, true)));
qs("#rule-search-input").addEventListener("input", (event) => {
  state.ruleQuery = event.target.value;
  dashboard.renderRuleList();
});
qs("#records-prev-button").addEventListener("click", () => dashboard.changePage(-1).catch((error) => setAction(error.message, true)));
qs("#records-next-button").addEventListener("click", () => dashboard.changePage(1).catch((error) => setAction(error.message, true)));

dashboard.refreshAll().catch((error) => setAction(`初始化失败: ${error.message}`, true));
