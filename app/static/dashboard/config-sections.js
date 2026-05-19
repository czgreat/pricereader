import { dashboard } from "./core.js";

const {
  state,
  qs,
  qsa,
  splitLines,
  joinLines,
  formatDate,
  formatNumber,
  escapeAttr,
  escapeHtml,
  statusPill,
  miniCard,
  validateIdentifier,
  validateFileName,
  validatePositiveNumber,
  sourceControl,
  sourceHealth,
  defaultSourceFileName,
  defaultRuleFileName,
  emptySource,
  emptyRule,
  findSource,
  findRule,
  setAction,
  fetchJson,
} = dashboard;

dashboard.selectSource = function selectSource(sourceKey) {
  state.selectedSourceKey = sourceKey;
  state.sourceMode = "edit";
  dashboard.renderSourceList();
  dashboard.renderSourceForm();
};

dashboard.renderSourceList = function renderSourceList() {
  const items = state.bootstrap.sources || [];
  if (!state.selectedSourceKey && items.length) state.selectedSourceKey = items[0].source_key;
  qs("#source-list").innerHTML = items.map((source) => {
    const control = sourceControl(source.source_key);
    const health = sourceHealth(source.source_key);
    return `
      <button type="button" class="select-card ${state.selectedSourceKey === source.source_key && state.sourceMode === "edit" ? "active" : ""}" data-source-key="${escapeAttr(source.source_key)}">
        <div class="select-card-title">${escapeHtml(source.label || source.source_key)}</div>
        <div class="select-card-meta">${escapeHtml(source.source_key)}</div>
        <div class="inline-flags">
          ${statusPill(source.enabled ? "enabled" : "disabled")}
          ${statusPill(control?.paused ? "paused" : (health?.status || "idle"))}
        </div>
        <div class="select-card-meta">${escapeHtml(`频率 ${formatNumber(source.interval_minutes)} 分钟 · 抓取条数 ${formatNumber(source.max_items)} · 最近成功 ${formatDate(health?.last_success_at)}`)}</div>
      </button>
    `;
  }).join("") || '<div class="empty">没有来源配置。</div>';
  qsa("[data-source-key]").forEach((node) => node.addEventListener("click", () => dashboard.selectSource(node.dataset.sourceKey)));
};

dashboard.renderSourceForm = function renderSourceForm() {
  const source = state.sourceMode === "create" ? emptySource() : findSource(state.selectedSourceKey);
  if (!source) return;
  const control = sourceControl(source.source_key);
  const health = sourceHealth(source.source_key);
  qs("#source-summary-cards").innerHTML = state.sourceMode === "create"
    ? [
        miniCard("当前模式", "新建来源", "先确认文件名与来源标识，再补执行参数", "tone-warn"),
        miniCard("默认频率", "12 分钟", "可根据来源稳定性再调", "tone-warn"),
        miniCard("默认条数", "3 条", "避免一开始抓太宽", "tone-warn"),
      ].join("")
    : [
        miniCard("运行状态", source.enabled ? "启用" : "停用", `调度 ${control?.paused ? "暂停" : "运行"} · 健康 ${dashboard.STATUS_LABELS[String(health?.status || "idle").toLowerCase()] || health?.status || "空闲"}`, source.enabled && !control?.paused ? "tone-ok" : "tone-warn"),
        miniCard("抓取参数", `${formatNumber(source.interval_minutes)} 分钟 / ${formatNumber(source.max_items)} 条`, `页数 ${formatNumber(source.pages)} · Cookie ${source.require_cookie ? "必需" : "可选"}`, "tone-ok"),
        miniCard("最近结果", `${formatNumber(health?.fetched_items)} 条`, `最近成功 ${formatDate(health?.last_success_at)} · 失败 ${formatNumber(health?.consecutive_failures)}`, health?.consecutive_failures ? "tone-bad" : "tone-ok"),
      ].join("");
  qs("#source_file_name").value = qs("#source_file_name").value || defaultSourceFileName(source.source_key);
  qs("#source_key").value = source.source_key || "";
  qs("#source_key").disabled = state.sourceMode !== "create";
  qs("#source_label").value = source.label || "";
  qs("#source_mode").value = source.mode || "";
  qs("#source_enabled").checked = Boolean(source.enabled);
  qs("#source_url").value = source.url || "";
  qs("#source_feed_url").value = source.feed_url || "";
  qs("#source_interval").value = source.interval_minutes ?? "";
  qs("#source_max_items").value = source.max_items ?? "";
  qs("#source_pages").value = source.pages ?? "";
  qs("#source_cookie_mode").value = source.cookie_mode || "";
  qs("#source_require_cookie").checked = Boolean(source.require_cookie);
  qs("#source_keywords").value = joinLines(source.keywords);
  qs("#source_notes").value = joinLines(source.notes || []);
  qs("#source-toggle-button").disabled = state.sourceMode === "create";
  qs("#source-sync-button").disabled = state.sourceMode === "create";
  qs("#source-delete-button").disabled = state.sourceMode === "create";
  qs("#source-duplicate-button").disabled = state.sourceMode === "create";
  qs("#source-flags").innerHTML = state.sourceMode === "create"
    ? '<span class="pill warn">新建模式</span>'
    : `${statusPill(source.enabled ? "enabled" : "disabled")} ${statusPill(control?.paused ? "paused" : "running")} ${statusPill(health?.status || "idle")} <span class="pill warn">退避至 ${escapeHtml(formatDate(health?.backoff_until))}</span>`;
  if (state.sourceMode === "create") {
    qs("#source-helper").textContent = "新建来源时建议先确认文件名和来源标识，再保存。";
  } else if (source.source_key.includes("smzdm")) {
    const note = (health?.fetched_items || 0) === 0
      ? (source.keywords?.length
          ? "什么值得买接口正常，但当前关键词筛选结果为 0 条。"
          : "什么值得买接口正常，当前抓取结果为 0 条，说明这一轮 RSS 暂无新候选。")
      : `什么值得买接口正常，最近一轮抓到 ${health?.fetched_items ?? 0} 条候选。`;
    qs("#source-helper").textContent = note;
  } else {
    qs("#source-helper").textContent = `最近成功时间：${formatDate(health?.last_success_at)}，最近抓取 ${formatNumber(health?.fetched_items)} 条。`;
  }
};

dashboard.enterCreateSourceMode = function enterCreateSourceMode() {
  state.sourceMode = "create";
  state.selectedSourceKey = null;
  qs("#source_file_name").value = defaultSourceFileName();
  dashboard.renderSourceList();
  dashboard.renderSourceForm();
  setAction("已切到来源新建模式");
};

dashboard.duplicateSource = async function duplicateSource() {
  const sourceKey = qs("#source_key").value.trim();
  if (!sourceKey || state.sourceMode === "create") return;
  const newKey = window.prompt("输入新来源标识", `${sourceKey}_copy`);
  if (!newKey) return;
  validateIdentifier(newKey, "来源标识");
  const fileName = qs("#source_file_name").value.trim() || defaultSourceFileName(sourceKey);
  validateFileName(fileName);
  await fetchJson(`/api/v1/sources/${encodeURIComponent(sourceKey)}/duplicate?new_key=${encodeURIComponent(newKey)}&file_name=${encodeURIComponent(fileName)}`, { method: "POST" });
  await dashboard.refreshAll();
  state.selectedSourceKey = newKey;
  dashboard.renderSourceList();
  dashboard.renderSourceForm();
  setAction(`来源 ${sourceKey} 已复制为 ${newKey}`);
};

dashboard.selectRule = function selectRule(ruleKey) {
  state.selectedRuleKey = ruleKey;
  state.ruleMode = "edit";
  state.activeRulePanel = "basic";
  dashboard.renderRuleList();
  dashboard.renderRuleForm();
};

dashboard.filteredRules = function filteredRules() {
  const query = String(state.ruleQuery || "").trim().toLowerCase();
  const items = state.bootstrap?.rules || [];
  if (!query) return items;
  return items.filter((rule) => JSON.stringify(rule).toLowerCase().includes(query));
};

dashboard.switchRulePanel = function switchRulePanel(panel) {
  state.activeRulePanel = panel;
  qsa("[data-rule-editor-panel]").forEach((node) => {
    node.classList.toggle("active", node.dataset.ruleEditorPanel === panel);
  });
};

dashboard.renderRuleList = function renderRuleList() {
  const allItems = state.bootstrap.rules || [];
  const items = dashboard.filteredRules();
  qs("#rule-search-input").value = state.ruleQuery || "";
  if (!state.selectedRuleKey && items.length) state.selectedRuleKey = items[0].rule_key;
  if (state.ruleMode !== "create" && items.length && !items.some((rule) => rule.rule_key === state.selectedRuleKey)) {
    state.selectedRuleKey = items[0].rule_key;
  }
  qs("#rule-list-count").textContent = `当前显示 ${items.length} / 总规则 ${allItems.length}`;
  qs("#rule-list").innerHTML = items.map((rule) => `
    <button type="button" class="select-card ${state.selectedRuleKey === rule.rule_key && state.ruleMode === "edit" ? "active" : ""}" data-rule-key="${escapeAttr(rule.rule_key)}">
      <div class="select-card-title">${escapeHtml(rule.rule_key)}</div>
      <div class="inline-flags">
        ${statusPill(rule.enabled ? "enabled" : "disabled")}
        <span class="pill warn">${escapeHtml(rule.priority || "P1")}</span>
      </div>
      <div class="select-card-meta">${escapeHtml(`来源 ${rule.sources.length} · 包含词 ${rule.include_keywords.length} · 排除词 ${rule.exclude_keywords.length}`)}</div>
      <div class="select-card-meta">${escapeHtml(`价格 ${formatNumber(rule.price?.min_cny)} - ${formatNumber(rule.price?.max_cny)} 元 · 规格 ${formatNumber(rule.spec?.value_g)}g · 冷却 ${formatNumber(rule.notify?.cooldown_hours)}h`)}</div>
    </button>
  `).join("") || '<div class="empty">当前搜索条件下没有规则。你可以直接点上方“新建规则”。</div>';
  qsa("[data-rule-key]").forEach((node) => node.addEventListener("click", () => dashboard.selectRule(node.dataset.ruleKey)));
};

dashboard.renderRuleForm = function renderRuleForm() {
  const rule = state.ruleMode === "create" ? emptyRule() : findRule(state.selectedRuleKey);
  if (!rule) return;
  qs("#rule-summary-cards").innerHTML = state.ruleMode === "create"
    ? [
        miniCard("当前模式", "新建规则", "先定标识，再补来源范围与阈值", "tone-warn"),
        miniCard("默认优先级", "P1", "可在保存前调整", "tone-warn"),
        miniCard("默认冷却", "2h", "默认 2 小时，也可以在右侧手动改", "tone-warn"),
      ].join("")
    : [
        miniCard("规则状态", rule.enabled ? "启用" : "停用", `优先级 ${rule.priority || "P1"} · 来源 ${rule.sources.length} 个`, rule.enabled ? "tone-ok" : "tone-warn"),
        miniCard("关键词规模", `${rule.include_keywords.length} / ${rule.exclude_keywords.length}`, `包含词 / 排除词，别名 ${rule.alias_keywords.length} 个`, rule.include_keywords.length ? "tone-ok" : "tone-warn"),
        miniCard("阈值", `${formatNumber(rule.price?.min_cny)} - ${formatNumber(rule.price?.max_cny)} 元`, `规格 ${formatNumber(rule.spec?.value_g)}g · 冷却 ${formatNumber(rule.notify?.cooldown_hours)}h`, rule.price?.min_cny !== null || rule.price?.max_cny !== null ? "tone-ok" : "tone-warn"),
      ].join("");
  qs("#rule_file_name").value = qs("#rule_file_name").value || defaultRuleFileName();
  qs("#rule_key").value = rule.rule_key || "";
  qs("#rule_key").disabled = state.ruleMode !== "create";
  qs("#rule_priority").value = rule.priority || "";
  qs("#rule_enabled").checked = Boolean(rule.enabled);
  qs("#rule_include_keywords").value = joinLines(rule.include_keywords);
  qs("#rule_alias_keywords").value = joinLines(rule.alias_keywords);
  qs("#rule_exclude_keywords").value = joinLines(rule.exclude_keywords);
  qs("#rule_spec_mode").value = rule.spec?.mode || "";
  qs("#rule_spec_value_g").value = rule.spec?.value_g ?? "";
  qs("#rule_spec_aliases").value = joinLines(rule.spec?.aliases || []);
  qs("#rule_price_mode").value = rule.price?.mode || "final_payable";
  qs("#rule_price_min_cny").value = rule.price?.min_cny ?? "";
  qs("#rule_price_max_cny").value = rule.price?.max_cny ?? "";
  qs("#rule_cooldown_hours").value = rule.notify?.cooldown_hours ?? 2;
  qs("#rule-delete-button").disabled = state.ruleMode === "create";
  qs("#rule-duplicate-button").disabled = state.ruleMode === "create";
  const selectedSources = new Set(rule.sources || []);
  qs("#rule_sources").innerHTML = (state.bootstrap.sources || []).map((source) => `
    <label>
      <input type="checkbox" value="${escapeAttr(source.source_key)}" ${selectedSources.has(source.source_key) ? "checked" : ""}>
      <span>${escapeHtml(source.label || source.source_key)}</span>
    </label>
  `).join("") || '<div class="empty">没有来源可选。</div>';
  const includeText = rule.include_keywords.length ? `包含 ${rule.include_keywords.join(" / ")}` : "先填包含词";
  const aliasText = rule.alias_keywords.length ? `别名 ${rule.alias_keywords.join(" / ")}` : "可选别名";
  const excludeText = rule.exclude_keywords.length ? `排除 ${rule.exclude_keywords.join(" / ")}` : "暂无排除词";
  let priceText = "不限制价格";
  if (rule.price?.min_cny !== null && rule.price?.min_cny !== undefined && rule.price?.max_cny !== null && rule.price?.max_cny !== undefined) {
    priceText = `价格在 ${formatNumber(rule.price.min_cny)} 到 ${formatNumber(rule.price.max_cny)} 元之间`;
  } else if (rule.price?.min_cny !== null && rule.price?.min_cny !== undefined) {
    priceText = `价格不低于 ${formatNumber(rule.price.min_cny)} 元`;
  } else if (rule.price?.max_cny !== null && rule.price?.max_cny !== undefined) {
    priceText = `价格不高于 ${formatNumber(rule.price.max_cny)} 元`;
  }
  let specText = "不限制规格";
  if (rule.spec?.mode === "equivalent") {
    specText = rule.spec?.value_g ? `按 ${formatNumber(rule.spec.value_g)} 克匹配` : "按克重匹配";
  } else if (rule.spec?.mode === "model") {
    specText = rule.spec?.aliases?.length ? `按型号 ${rule.spec.aliases.join(" / ")}` : "按型号关键词匹配";
  }
  qs("#rule-summary-preview").innerHTML = `
    <strong>当前规则一句话</strong>
    <div>${escapeHtml(`${includeText}；${aliasText}；${excludeText}；${priceText}；${specText}；${formatNumber(rule.notify?.cooldown_hours || 2)} 小时内不重复提醒。`)}</div>
  `;
  dashboard.switchRulePanel(state.activeRulePanel || "basic");
};

dashboard.enterCreateRuleMode = function enterCreateRuleMode() {
  state.ruleMode = "create";
  state.selectedRuleKey = null;
  state.activeRulePanel = "basic";
  qs("#rule_file_name").value = defaultRuleFileName();
  dashboard.renderRuleList();
  dashboard.renderRuleForm();
  setAction("已切到规则新建模式");
};

dashboard.duplicateRule = async function duplicateRule() {
  const ruleKey = qs("#rule_key").value.trim();
  if (!ruleKey || state.ruleMode === "create") return;
  const newKey = window.prompt("输入新规则标识", `${ruleKey}_copy`);
  if (!newKey) return;
  validateIdentifier(newKey, "规则标识");
  const fileName = qs("#rule_file_name").value.trim() || defaultRuleFileName();
  validateFileName(fileName);
  await fetchJson(`/api/v1/rules/${encodeURIComponent(ruleKey)}/duplicate?new_key=${encodeURIComponent(newKey)}&file_name=${encodeURIComponent(fileName)}`, { method: "POST" });
  await dashboard.refreshAll();
  state.selectedRuleKey = newKey;
  state.activeRulePanel = "basic";
  dashboard.renderRuleList();
  dashboard.renderRuleForm();
  setAction(`规则 ${ruleKey} 已复制为 ${newKey}`);
};

dashboard.saveSourceConfig = async function saveSourceConfig(event) {
  event.preventDefault();
  const sourceKey = qs("#source_key").value.trim();
  const fileName = qs("#source_file_name").value.trim() || defaultSourceFileName(sourceKey);
  validateFileName(fileName);
  validateIdentifier(sourceKey, "来源标识");
  validatePositiveNumber(qs("#source_interval").value, "抓取频率", 1, 1440);
  validatePositiveNumber(qs("#source_max_items").value, "抓取条数", 1, 50);
  validatePositiveNumber(qs("#source_pages").value, "页数", 1, 20);
  const payload = {
    source_key: sourceKey,
    label: qs("#source_label").value,
    mode: qs("#source_mode").value,
    enabled: qs("#source_enabled").checked,
    url: qs("#source_url").value,
    feed_url: qs("#source_feed_url").value,
    interval_minutes: qs("#source_interval").value ? Number(qs("#source_interval").value) : null,
    max_items: qs("#source_max_items").value ? Number(qs("#source_max_items").value) : null,
    pages: qs("#source_pages").value ? Number(qs("#source_pages").value) : null,
    cookie_mode: qs("#source_cookie_mode").value,
    require_cookie: qs("#source_require_cookie").checked,
    keywords: splitLines(qs("#source_keywords").value),
    notes: splitLines(qs("#source_notes").value),
  };
  if (state.sourceMode === "create") {
    setAction(`新建来源 ${sourceKey}...`);
    await fetchJson(`/api/v1/sources/config?file_name=${encodeURIComponent(fileName)}`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  } else {
    setAction(`保存来源 ${sourceKey}...`);
    await fetchJson(`/api/v1/sources/${encodeURIComponent(sourceKey)}/config`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  }
  await dashboard.refreshAll();
  state.selectedSourceKey = sourceKey;
  state.sourceMode = "edit";
  dashboard.renderSourceList();
  dashboard.renderSourceForm();
  setAction(`来源 ${sourceKey} 已保存`);
};

dashboard.deleteSourceConfig = async function deleteSourceConfig() {
  const sourceKey = qs("#source_key").value.trim();
  if (!sourceKey || state.sourceMode === "create") return;
  if (!window.confirm(`确认删除来源 ${sourceKey} 吗？`)) return;
  await fetchJson(`/api/v1/sources/${encodeURIComponent(sourceKey)}/config`, { method: "DELETE" });
  state.selectedSourceKey = null;
  state.sourceMode = "create";
  await dashboard.refreshAll();
  dashboard.enterCreateSourceMode();
  setAction(`来源 ${sourceKey} 已删除`);
};

dashboard.toggleSourcePause = async function toggleSourcePause() {
  const sourceKey = qs("#source_key").value.trim();
  if (!sourceKey || state.sourceMode === "create") return;
  const control = sourceControl(sourceKey);
  const paused = Boolean(control?.paused);
  await fetchJson(`/api/v1/sources/${encodeURIComponent(sourceKey)}/${paused ? "resume" : "pause"}`, {
    method: "PUT",
    body: JSON.stringify({ reason: paused ? "resume from ui" : "pause from ui" }),
  });
  await dashboard.refreshAll();
  state.selectedSourceKey = sourceKey;
  dashboard.renderSourceList();
  dashboard.renderSourceForm();
  setAction(`来源 ${sourceKey} 已${paused ? "恢复" : "暂停"}`);
};

dashboard.syncSourceNow = async function syncSourceNow() {
  const sourceKey = qs("#source_key").value.trim();
  if (!sourceKey || state.sourceMode === "create") return;
  const maxItems = qs("#source_max_items").value ? Number(qs("#source_max_items").value) : "";
  const query = maxItems ? `?max_items=${encodeURIComponent(maxItems)}` : "";
  await fetchJson(`/api/v1/sources/${encodeURIComponent(sourceKey)}/retry-sync${query}`, { method: "POST" });
  await dashboard.refreshAll();
  state.selectedSourceKey = sourceKey;
  dashboard.renderSourceList();
  dashboard.renderSourceForm();
  setAction(`来源 ${sourceKey} 已同步`);
};

dashboard.saveRuleConfig = async function saveRuleConfig(event) {
  event.preventDefault();
  const ruleKey = qs("#rule_key").value.trim();
  const fileName = qs("#rule_file_name").value.trim() || defaultRuleFileName();
  validateFileName(fileName);
  validateIdentifier(ruleKey, "规则标识");
  validatePositiveNumber(qs("#rule_price_min_cny").value, "价格下限", 0, 1000000);
  validatePositiveNumber(qs("#rule_spec_value_g").value, "规格克重", 0, 1000000);
  validatePositiveNumber(qs("#rule_price_max_cny").value, "价格上限", 0, 1000000);
  validatePositiveNumber(qs("#rule_cooldown_hours").value, "通知冷却", 1, 720);
  const specMode = qs("#rule_spec_mode").value;
  const specAliases = splitLines(qs("#rule_spec_aliases").value);
  let specPayload = null;
  if (specMode === "equivalent") {
    specPayload = {
      mode: "equivalent",
      value_g: qs("#rule_spec_value_g").value ? Number(qs("#rule_spec_value_g").value) : null,
      aliases: specAliases,
    };
  } else if (specMode === "model") {
    specPayload = {
      mode: "model",
      value_g: null,
      aliases: specAliases,
    };
  }
  const payload = {
    rule_key: ruleKey,
    enabled: qs("#rule_enabled").checked,
    priority: qs("#rule_priority").value,
    sources: qsa("#rule_sources input[type=\"checkbox\"]:checked").map((node) => node.value),
    include_keywords: splitLines(qs("#rule_include_keywords").value),
    alias_keywords: splitLines(qs("#rule_alias_keywords").value),
    exclude_keywords: splitLines(qs("#rule_exclude_keywords").value),
    spec: specPayload,
    price: {
      mode: qs("#rule_price_mode").value || "final_payable",
      min_cny: qs("#rule_price_min_cny").value ? Number(qs("#rule_price_min_cny").value) : null,
      max_cny: qs("#rule_price_max_cny").value ? Number(qs("#rule_price_max_cny").value) : null,
    },
    notify: {
      cooldown_hours: qs("#rule_cooldown_hours").value ? Number(qs("#rule_cooldown_hours").value) : 2,
    },
  };
  if (state.ruleMode === "create") {
    await fetchJson(`/api/v1/rules/config?file_name=${encodeURIComponent(fileName)}`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  } else {
    await fetchJson(`/api/v1/rules/${encodeURIComponent(ruleKey)}/config`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  }
  await dashboard.refreshAll();
  state.selectedRuleKey = ruleKey;
  state.ruleMode = "edit";
  dashboard.renderRuleList();
  dashboard.renderRuleForm();
  setAction(`规则 ${ruleKey} 已保存`);
};

dashboard.deleteRuleConfig = async function deleteRuleConfig() {
  const ruleKey = qs("#rule_key").value.trim();
  if (!ruleKey || state.ruleMode === "create") return;
  if (!window.confirm(`确认删除规则 ${ruleKey} 吗？`)) return;
  await fetchJson(`/api/v1/rules/${encodeURIComponent(ruleKey)}/config`, { method: "DELETE" });
  state.selectedRuleKey = null;
  state.ruleMode = "create";
  await dashboard.refreshAll();
  dashboard.enterCreateRuleMode();
  setAction(`规则 ${ruleKey} 已删除`);
};
