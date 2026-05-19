import { dashboard } from "./core.js";

const {
  state,
  qs,
  qsa,
  escapeHtml,
  formatDate,
  formatNumber,
  externalLink,
  encodeTitle,
  recordCard,
  statusPill,
  setAction,
  fetchJson,
  STATUS_LABELS,
} = dashboard;

dashboard.renderHistorySummary = function renderHistorySummary(matches) {
  const items = matches || [];
  const latest = items[0] || null;
  const today = items.filter((item) => String(item.evaluated_at || "").slice(0, 10) === new Date().toISOString().slice(0, 10));
  qs("#history-summary").innerHTML = `
    <article class="history-stat">
      <span>当前页命中</span>
      <strong>${items.length}</strong>
      <div class="muted">当前筛选条件下展示的命中记录</div>
    </article>
    <article class="history-stat">
      <span>今日命中</span>
      <strong>${today.length}</strong>
      <div class="muted">以 UTC 日期计算</div>
    </article>
    <article class="history-stat">
      <span>最新价格</span>
      <strong>${escapeHtml(latest && latest.used_price_amount !== null ? latest.used_price_amount : "-")}</strong>
      <div class="muted">${escapeHtml(latest ? latest.rule_key : "暂无命中")}</div>
    </article>
    <article class="history-stat">
      <span>最近来源</span>
      <strong>${escapeHtml(latest ? latest.source_key : "-")}</strong>
      <div class="muted">${escapeHtml(latest ? formatDate(latest.evaluated_at) : "暂无命中")}</div>
    </article>
  `;
};

dashboard.renderHistoryChips = function renderHistoryChips() {
  const chips = [
    { key: "all", label: "全部命中" },
    { key: "with_price", label: "有价格" },
    { key: "today", label: "今日命中" },
    { key: "smzdm", label: "什么值得买" },
    { key: "douban", label: "豆瓣" },
  ];
  qs("#history-chips").innerHTML = chips.map((chip) => `
    <button type="button" class="chip ${state.historyFilter === chip.key ? "active" : ""}" data-history-filter="${chip.key}">${chip.label}</button>
  `).join("");
  qsa("[data-history-filter]").forEach((node) => {
    node.addEventListener("click", () => {
      state.historyFilter = node.dataset.historyFilter;
      dashboard.renderRecords({ reload: false }).catch((error) => setAction(error.message, true));
    });
  });
};

dashboard.applyHistoryFilter = function applyHistoryFilter(items) {
  const today = new Date().toISOString().slice(0, 10);
  if (state.historyFilter === "with_price") {
    return items.filter((item) => item.used_price_amount !== null && item.used_price_amount !== undefined);
  }
  if (state.historyFilter === "today") {
    return items.filter((item) => String(item.evaluated_at || "").slice(0, 10) === today);
  }
  if (state.historyFilter === "smzdm") {
    return items.filter((item) => String(item.source_key || "").includes("smzdm"));
  }
  if (state.historyFilter === "douban") {
    return items.filter((item) => String(item.source_key || "").includes("douban"));
  }
  return items;
};

dashboard.updatePagerStatus = function updatePagerStatus(visibleCount = null) {
  const page = state.paging[state.activeTab];
  const current = Math.floor(page.offset / page.limit) + 1;
  const totalPages = Math.max(1, Math.ceil((page.total || 0) / page.limit));
  const pageCount = Array.isArray(page.items) ? page.items.length : 0;
  if (visibleCount !== null) {
    const filteredText = visibleCount === pageCount
      ? `第 ${current} / ${totalPages} 页 · 当前页 ${visibleCount} 条 · 共 ${page.total} 条`
      : `第 ${current} / ${totalPages} 页 · 当前页筛后 ${visibleCount} / ${pageCount} 条 · 共 ${page.total} 条`;
    qs("#records-page-status").textContent = filteredText;
  } else {
    qs("#records-page-status").textContent = `第 ${current} / ${totalPages} 页 · 共 ${page.total} 条`;
  }
  qs("#records-prev-button").disabled = page.offset <= 0;
  qs("#records-next-button").disabled = page.offset + page.limit >= page.total;
};

dashboard.loadRecords = async function loadRecords(tab = state.activeTab) {
  const page = state.paging[tab];
  const params = new URLSearchParams({ offset: String(page.offset), limit: String(page.limit) });
  const sourceValue = qs("#record-source-filter")?.value || "";
  const ruleValue = qs("#record-rule-filter")?.value || "";
  if (sourceValue) params.set("source_key", sourceValue);
  if (ruleValue && ["evaluations", "matches", "notifications"].includes(tab)) params.set("rule_key", ruleValue);

  const endpointMap = {
    stored: "/api/v1/stored-items",
    evaluations: "/api/v1/evaluations",
    matches: "/api/v1/matches",
    notifications: "/api/v1/notifications",
    health: "/api/v1/source-health",
    audit: "/api/v1/config-audit",
  };
  const requestId = ++state.recordRequestId;
  const data = await fetchJson(`${endpointMap[tab]}?${params.toString()}`);
  if (requestId !== state.recordRequestId || tab !== state.activeTab) {
    return false;
  }
  state.paging[tab] = {
    ...state.paging[tab],
    offset: data.offset,
    limit: data.limit,
    total: data.total,
    items: data.items,
  };
  return true;
};

dashboard.buildRecordFilters = function buildRecordFilters() {
  const sourceSelect = qs("#record-source-filter");
  const ruleSelect = qs("#record-rule-filter");
  const queryInput = qs("#record-query-filter");
  const currentSource = sourceSelect.value;
  const currentRule = ruleSelect.value;
  const currentQuery = queryInput.value;
  sourceSelect.innerHTML = ['<option value="">全部来源</option>']
    .concat((state.bootstrap.sources || []).map((source) => `<option value="${dashboard.escapeAttr(source.source_key)}">${dashboard.escapeHtml(source.label || source.source_key)}</option>`))
    .join("");
  ruleSelect.innerHTML = ['<option value="">全部规则</option>']
    .concat((state.bootstrap.rules || []).map((rule) => `<option value="${dashboard.escapeAttr(rule.rule_key)}">${dashboard.escapeHtml(rule.rule_key)}</option>`))
    .join("");
  sourceSelect.value = currentSource || "";
  ruleSelect.value = currentRule || "";
  queryInput.value = currentQuery || "";
  sourceSelect.onchange = async () => { state.paging[state.activeTab].offset = 0; await dashboard.renderRecords(); };
  ruleSelect.onchange = async () => { state.paging[state.activeTab].offset = 0; await dashboard.renderRecords(); };
  queryInput.oninput = () => dashboard.renderRecords({ reload: false }).catch((error) => setAction(error.message, true));
};

dashboard.renderRecordItems = function renderRecordItems(items, renderer) {
  if (!items.length) return '<div class="empty">当前筛选条件下没有记录。</div>';
  return items.map(renderer).join("");
};

dashboard.filterCurrentPageItems = function filterCurrentPageItems(items) {
  const query = (qs("#record-query-filter")?.value || "").trim().toLowerCase();
  if (!query) return items;
  return items.filter((item) => JSON.stringify(item).toLowerCase().includes(query));
};

dashboard.renderRecords = async function renderRecords(options = {}) {
  const { reload = true } = options;
  const tab = state.activeTab;
  if (reload) {
    const applied = await dashboard.loadRecords(tab);
    if (!applied) return;
  }
  const primary = qs("#records-primary");
  const secondary = qs("#records-secondary");
  qsa(".subtab").forEach((node) => node.classList.toggle("active", node.dataset.tab === tab));
  let items = dashboard.filterCurrentPageItems(state.paging[tab].items);
  if (tab === "matches") {
    items = dashboard.applyHistoryFilter(items);
  }
  const recordTitles = {
    stored: ["记录中心", "最近抓到的条目与当前页过滤"],
    evaluations: ["评估记录", "按来源、规则和关键词查看当前页评估结果"],
    matches: ["好价历史", "检测到的好价命中记录与详情"],
    notifications: ["通知记录", "最近推送结果与失败信息"],
    health: ["来源健康", "抓取健康度与调度状态"],
    audit: ["配置审计", "来源、规则、运行时配置的改动轨迹"],
  };
  qs("#records-title").textContent = recordTitles[tab][0];
  qs("#records-subtitle").textContent = recordTitles[tab][1];

  if (tab === "stored") {
    primary.innerHTML = dashboard.renderRecordItems(items, (item) => recordCard(
      externalLink(item.url, encodeTitle(item.title)),
      statusPill(item.source_key),
      [`作者 ${item.author_name || "-"} · 回复 ${formatNumber(item.reply_count)} · 出现次数 ${formatNumber(item.seen_count)}`, `最近活跃 ${item.last_active_text || "-"} · 首次入库 ${formatDate(item.first_seen_at)}`],
      item,
    ));
    secondary.innerHTML = `<article class="record-item"><h4>最近 24 小时</h4><div class="record-meta">抓取 ${formatNumber(state.bootstrap.stats_24h.sync_runs)} 次 · 新增 ${formatNumber(state.bootstrap.stats_24h.inserted_items)} 条</div><div class="record-meta">命中 ${formatNumber(state.bootstrap.stats_24h.matched_items)} 条 · 通知成功 ${formatNumber(state.bootstrap.stats_24h.notifications_sent)} 次</div></article>`;
  } else if (tab === "evaluations") {
    primary.innerHTML = dashboard.renderRecordItems(items, (item) => recordCard(
      escapeHtml(item.external_id),
      statusPill(item.matched ? "matched" : item.reason),
      [`${item.source_key} · 规则 ${item.rule_key}`, `命中词 ${(item.matched_keywords || []).join(", ") || "-"} · 排除词 ${(item.excluded_keywords || []).join(", ") || "-"}`],
      item,
    ));
    secondary.innerHTML = '<div class="empty">点击左侧记录可查看结构化详情。</div>';
  } else if (tab === "matches") {
    dashboard.renderHistorySummary(items);
    dashboard.renderHistoryChips();
    primary.innerHTML = dashboard.renderRecordItems(items, (item) => recordCard(
      externalLink(item.url, encodeTitle(item.title)),
      statusPill(item.rule_key),
      [`${item.source_key} · 价格 ${formatNumber(item.used_price_amount)} · 规格 ${formatNumber(item.used_spec_grams)}`, `最近看到 ${formatDate(item.last_seen_at)} · 出现次数 ${formatNumber(item.seen_count)}`],
      item,
    ));
    secondary.innerHTML = '<article class="record-item"><h4>筛选建议</h4><div class="record-meta">可先按来源和规则筛，再用关键词搜索当前页结果。点击任意命中项，右侧会显示结构化详情、图片和通知历史。</div></article>';
  } else if (tab === "notifications") {
    qs("#history-summary").innerHTML = "";
    qs("#history-chips").innerHTML = "";
    primary.innerHTML = dashboard.renderRecordItems(items, (item) => recordCard(
      escapeHtml(encodeTitle(item.title)),
      statusPill(item.status),
      [`${item.source_key} · ${item.rule_key}`, `${formatDate(item.updated_at)} · ${item.error_message || "发送完成"}`],
      item,
    ));
    secondary.innerHTML = '<div class="empty">这里展示最近通知结果，支持按来源和规则筛选。</div>';
  } else if (tab === "health") {
    qs("#history-summary").innerHTML = "";
    qs("#history-chips").innerHTML = "";
    primary.innerHTML = dashboard.renderRecordItems(items, (item) => recordCard(
      escapeHtml(item.source_key),
      statusPill(item.status),
      [`抓取 ${formatNumber(item.fetched_items)} · 新增 ${formatNumber(item.inserted_items)} · 更新 ${formatNumber(item.updated_items)}`, `失败 ${formatNumber(item.consecutive_failures)} · 退避 ${formatDate(item.backoff_until)}`],
      item,
    ));
    secondary.innerHTML = dashboard.renderRecordItems(state.bootstrap.scheduler.configured_sources || [], (item) => recordCard(
      escapeHtml(item.source_key),
      statusPill(item.paused ? "paused" : (item.enabled ? "enabled" : "disabled")),
      [`频率 ${formatNumber(item.interval_minutes)} 分钟 · 下一次 ${formatDate((state.bootstrap.scheduler.jobs || []).find((job) => job.id === `sync:${item.source_key}`)?.next_run_time)}`, `${item.pause_reason || "无暂停原因"}`],
      item,
    ));
  } else {
    qs("#history-summary").innerHTML = "";
    qs("#history-chips").innerHTML = "";
    primary.innerHTML = dashboard.renderRecordItems(items, (item) => recordCard(
      escapeHtml(`${STATUS_LABELS[item.action] || item.action} · ${item.entity_type} · ${item.entity_key}`),
      statusPill(item.action),
      [`操作者 ${item.actor} · 文件 ${item.file_name || "-"}`, `${formatDate(item.created_at)}`],
      item,
    ));
    secondary.innerHTML = '<div class="empty">审计记录保存配置变更的前后内容和时间。</div>';
  }

  if (tab !== "matches") {
    qs("#history-summary").innerHTML = "";
    qs("#history-chips").innerHTML = "";
  }

  dashboard.updatePagerStatus(items.length);
  dashboard.bindRecordSelection();
  await dashboard.renderRecordDetail();
};
