const state = {
  bootstrap: null,
  runtimeView: null,
  activeSection: "overview",
  selectedSourceKey: null,
  selectedRuleKey: null,
  activeTab: "stored",
  sourceMode: "edit",
  ruleMode: "edit",
  activeRulePanel: "basic",
  ruleQuery: "",
  recordDetail: null,
  historyFilter: "all",
  recordRequestId: 0,
  paging: {
    stored: { offset: 0, limit: 20, total: 0, items: [] },
    evaluations: { offset: 0, limit: 20, total: 0, items: [] },
    matches: { offset: 0, limit: 20, total: 0, items: [] },
    notifications: { offset: 0, limit: 20, total: 0, items: [] },
    health: { offset: 0, limit: 20, total: 0, items: [] },
    audit: { offset: 0, limit: 20, total: 0, items: [] },
  },
};

const SECTION_META = {
  overview: { title: "概览", subtitle: "自动化总览与 24 小时统计" },
  runtime: { title: "运行时设置", subtitle: "管理 Cookie、推送配置与敏感字段显示方式" },
  sources: { title: "来源配置", subtitle: "管理来源、同步频率、抓取条数与运行控制" },
  rules: { title: "规则配置", subtitle: "管理规则、价格阈值、关键词与冷却策略" },
  records: { title: "记录中心", subtitle: "查看好价历史、通知、健康状态与配置审计" },
};

const qs = (selector) => document.querySelector(selector);
const qsa = (selector) => Array.from(document.querySelectorAll(selector));
const splitLines = (value) => value.split("\n").map((item) => item.trim()).filter(Boolean);
const joinLines = (value) => (value || []).join("\n");
const formatDate = (value) => value || "-";
const formatNumber = (value) => value === null || value === undefined || value === "" ? "-" : value;
const yesNo = (flag) => (flag ? "已配置" : "未配置");

const STATUS_LABELS = {
  ok: "正常",
  success: "成功",
  sent: "已发送",
  matched: "命中",
  enabled: "启用",
  disabled: "停用",
  paused: "暂停",
  running: "运行中",
  active: "有效",
  muted: "静默",
  idle: "空闲",
  backoff: "退避中",
  skipped_cooldown: "冷却跳过",
  skipped_muted: "静默跳过",
  error: "异常",
  failed: "失败",
  missing_keywords: "缺少关键词",
  excluded_keyword_hit: "命中排除词",
  source_not_allowed: "来源不匹配",
  create: "新建",
  update: "更新",
  delete: "删除",
  duplicate: "复制",
};

const sensitiveFields = ["douban_cookie", "smzdm_cookie", "wechat_push_token", "wechat_target_id"];

function setAction(text, isError = false) {
  qs("#action-text").textContent = text;
  qs("#action-text").style.color = isError ? "var(--bad)" : "var(--muted)";
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(payload.detail || response.statusText);
  }
  return payload;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
}

function escapeAttr(value) {
  return escapeHtml(value);
}

function safeUrl(value) {
  const text = String(value ?? "").trim();
  if (!text) return "";
  try {
    const parsed = new URL(text, window.location.origin);
    if (["http:", "https:"].includes(parsed.protocol)) {
      return parsed.href;
    }
  } catch (_error) {
    return "";
  }
  return "";
}

function externalLink(url, label, className = "record-link") {
  const text = escapeHtml(label || url || "无链接");
  const resolved = safeUrl(url);
  if (!resolved) return text;
  return `<a class="${escapeAttr(className)}" href="${escapeAttr(resolved)}" target="_blank" rel="noreferrer">${text}</a>`;
}

function statusPill(value) {
  const normalized = String(value || "").toLowerCase();
  let klass = "warn";
  if (["ok", "success", "sent", "matched", "enabled", "active"].includes(normalized)) klass = "ok";
  if (["error", "failed", "backoff", "skipped_cooldown", "skipped_muted", "disabled", "paused", "muted"].includes(normalized)) klass = "bad";
  return `<span class="pill ${klass}">${escapeHtml(STATUS_LABELS[normalized] || value || "未知")}</span>`;
}

function miniCard(label, value, meta, tone = "") {
  return `
    <article class="mini-card ${tone}">
      <div class="mini-label">${escapeHtml(label)}</div>
      <strong>${escapeHtml(value)}</strong>
      <div class="mini-meta">${escapeHtml(meta)}</div>
    </article>
  `;
}

function booleanTone(flag) {
  return flag ? "tone-ok" : "tone-warn";
}

function firstUpcomingJob(jobs) {
  return (jobs || [])
    .filter((job) => job.next_run_time)
    .sort((left, right) => String(left.next_run_time).localeCompare(String(right.next_run_time)))[0] || null;
}

function syncSectionHeader() {
  const meta = SECTION_META[state.activeSection] || SECTION_META.overview;
  qs("#workspace-title").textContent = meta.title;
  qs("#workspace-subtitle").textContent = meta.subtitle;
  qsa(".workspace-section").forEach((node) => {
    node.classList.toggle("active", node.dataset.section === state.activeSection);
  });
  qsa("[data-section-nav]").forEach((node) => {
    const section = node.dataset.sectionNav;
    const tabTarget = node.dataset.tabTarget || "";
    const isActive = state.activeSection === section && (!tabTarget || tabTarget === state.activeTab);
    node.classList.toggle("active", isActive);
  });
}

function encodeRecord(payload) {
  return encodeURIComponent(JSON.stringify(payload));
}

function decodeRecord(payload) {
  return JSON.parse(decodeURIComponent(payload));
}

function validateIdentifier(value, label) {
  if (!/^[a-z0-9][a-z0-9_-]{2,79}$/.test(value)) {
    throw new Error(`${label} 必须是 3-80 位，只能包含小写字母、数字、下划线和中划线。`);
  }
}

function validateFileName(value) {
  if (!/^[A-Za-z0-9._-]+\.ya?ml$/.test(value) || value.includes("..") || value.includes("/")) {
    throw new Error("文件名必须是安全的 .yaml 文件名。");
  }
}

function validatePositiveNumber(value, label, min, max) {
  if (value === null || value === undefined || value === "") return;
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric < min || numeric > max) {
    throw new Error(`${label} 必须在 ${min} 到 ${max} 之间。`);
  }
}

function findSource(sourceKey) {
  return (state.bootstrap?.sources || []).find((item) => item.source_key === sourceKey) || null;
}

function findRule(ruleKey) {
  return (state.bootstrap?.rules || []).find((item) => item.rule_key === ruleKey) || null;
}

function sourceControl(sourceKey) {
  return (state.bootstrap?.source_controls || []).find((item) => item.source_key === sourceKey) || null;
}

function sourceHealth(sourceKey) {
  return (state.bootstrap?.source_health || []).find((item) => item.source_key === sourceKey) || null;
}

function defaultSourceFileName(sourceKey = "") {
  if (sourceKey.includes("douban")) return "douban.yaml";
  if (sourceKey.includes("smzdm")) return "smzdm.yaml";
  return "custom.yaml";
}

function defaultRuleFileName() {
  return "default.yaml";
}

function emptySource() {
  return {
    source_key: "",
    label: "",
    mode: "",
    enabled: true,
    url: "",
    feed_url: "",
    interval_minutes: 12,
    max_items: 3,
    pages: 1,
    cookie_mode: "",
    require_cookie: false,
    keywords: [],
    notes: [],
  };
}

function emptyRule() {
  return {
    rule_key: "",
    enabled: true,
    priority: "P1",
    sources: [],
    include_keywords: [],
    alias_keywords: [],
    exclude_keywords: [],
    spec: { mode: "equivalent", value_g: null, aliases: [] },
    price: { mode: "final_payable", max_cny: null },
    notify: { cooldown_hours: 2 },
  };
}

function encodeTitle(title) {
  return title || "未命名记录";
}

function recordCard(title, badge, metaLines, payload) {
  return `
    <article class="record-item" data-record='${escapeAttr(encodeRecord(payload))}'>
      <div class="record-item-top">
        <h4>${title}</h4>
        ${badge}
      </div>
      ${metaLines.map((line) => `<div class="record-meta">${escapeHtml(line)}</div>`).join("")}
    </article>
  `;
}

const dashboard = {
  state,
  SECTION_META,
  STATUS_LABELS,
  sensitiveFields,
  qs,
  qsa,
  splitLines,
  joinLines,
  formatDate,
  formatNumber,
  yesNo,
  setAction,
  fetchJson,
  escapeHtml,
  escapeAttr,
  safeUrl,
  externalLink,
  statusPill,
  miniCard,
  booleanTone,
  firstUpcomingJob,
  syncSectionHeader,
  encodeRecord,
  decodeRecord,
  validateIdentifier,
  validateFileName,
  validatePositiveNumber,
  findSource,
  findRule,
  sourceControl,
  sourceHealth,
  defaultSourceFileName,
  defaultRuleFileName,
  emptySource,
  emptyRule,
  encodeTitle,
  recordCard,
};

dashboard.switchSection = function switchSection(section, tabTarget = "") {
  state.activeSection = section;
  if (tabTarget) {
    state.activeTab = tabTarget;
    state.recordDetail = null;
    state.paging[state.activeTab].offset = 0;
  }
  if (section === "rules" && !state.activeRulePanel) {
    state.activeRulePanel = "basic";
  }
  syncSectionHeader();
  if (section === "records") {
    dashboard.renderRecords?.().catch((error) => setAction(error.message, true));
  }
};

export { dashboard };
