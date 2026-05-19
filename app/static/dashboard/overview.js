import { dashboard } from "./core.js";
import { buildRuntimePayload, fetchRuntimeConfigView } from "../shared/runtime-config.js";

const {
  state,
  qs,
  firstUpcomingJob,
  formatDate,
  formatNumber,
  yesNo,
  miniCard,
  booleanTone,
  setAction,
} = dashboard;

dashboard.renderOverview = function renderOverview() {
  const summary = state.bootstrap.summary;
  const runtime = state.runtimeView;
  const stats = state.bootstrap.stats_24h || {};
  const scheduler = state.bootstrap.scheduler || {};
  const configuredSources = scheduler.configured_sources || [];
  const nextJob = firstUpcomingJob(scheduler.jobs || []);
  const pausedCount = configuredSources.filter((item) => item.paused).length;
  const activeHealth = state.bootstrap.source_health || [];
  const unhealthyCount = activeHealth.filter((item) => {
    const normalized = String(item.status || "").toLowerCase();
    return ["error", "failed", "backoff"].includes(normalized) || Number(item.consecutive_failures || 0) > 0;
  }).length;
  qs("#version-text").textContent = `版本 ${summary.version} · 项目 ${summary.project}`;
  qs("#updated-text").textContent = `最近刷新 ${new Date().toLocaleString("zh-CN", { hour12: false })}`;
  qs("#metric-sources").textContent = summary.config.enabled_sources;
  qs("#metric-sources-sub").textContent = `总来源 ${summary.config.source_count} · 豆瓣 Cookie ${yesNo(runtime.configured.douban_cookie)}`;
  qs("#metric-rules").textContent = summary.config.enabled_rules;
  qs("#metric-rules-sub").textContent = `总规则 ${summary.config.rule_count} · 24 小时命中 ${formatNumber(stats.matched_items)}`;
  qs("#metric-items").textContent = formatNumber(stats.inserted_items);
  qs("#metric-items-sub").textContent = `24 小时新增 ${formatNumber(stats.inserted_items)} · 更新 ${formatNumber(stats.updated_items)}`;
  qs("#metric-notifications").textContent = formatNumber(stats.notifications_sent);
  qs("#metric-notifications-sub").textContent = `24 小时通知成功 ${formatNumber(stats.notifications_sent)} · 失败 ${formatNumber(stats.notifications_failed)}`;
  qs("#overview-hero-cards").innerHTML = [
    miniCard("命中", formatNumber(stats.matched_items), "过去 24 小时检测到的命中记录", stats.matched_items ? "tone-ok" : "tone-warn"),
    miniCard("下次任务", nextJob ? "已排队" : "待确认", nextJob ? `${nextJob.id} · ${formatDate(nextJob.next_run_time)}` : "当前没有拿到下一次调度信息", nextJob ? "tone-ok" : "tone-warn"),
  ].join("");
  qs("#overview-integrations").innerHTML = [
    miniCard("微信推送", runtime.configured.wechat_push_url && runtime.configured.wechat_push_token && runtime.configured.wechat_target_id ? "已接通" : "待补齐", "地址、令牌、目标标识三者都需要可用", runtime.configured.wechat_push_url && runtime.configured.wechat_push_token && runtime.configured.wechat_target_id ? "tone-ok" : "tone-warn"),
    miniCard("豆瓣 Cookie", yesNo(runtime.configured.douban_cookie), runtime.configured.douban_cookie ? "豆瓣白名单来源可走登录态" : "当前仍为空", booleanTone(runtime.configured.douban_cookie)),
    miniCard("SMZDM Cookie", yesNo(runtime.configured.smzdm_cookie), runtime.configured.smzdm_cookie ? "什么值得买登录态已配置" : "当前仍为空", booleanTone(runtime.configured.smzdm_cookie)),
  ].join("");
  qs("#overview-scheduler").innerHTML = [
    miniCard("启用来源", formatNumber(configuredSources.filter((item) => item.enabled).length), `暂停 ${pausedCount} 个 · 总配置 ${configuredSources.length} 个`, configuredSources.filter((item) => item.enabled).length ? "tone-ok" : "tone-warn"),
    miniCard("下一次同步", nextJob ? formatDate(nextJob.next_run_time) : "-", nextJob ? `任务 ${nextJob.id}` : "没有读取到已排队任务", nextJob ? "tone-ok" : "tone-warn"),
    miniCard("健康异常", formatNumber(unhealthyCount), unhealthyCount ? "建议进入“记录中心 / 健康”继续排查" : "当前没有明显异常来源", unhealthyCount ? "tone-bad" : "tone-ok"),
  ].join("");
  qs("#overview-activity").innerHTML = [
    miniCard("同步次数", formatNumber(stats.sync_runs), "过去 24 小时运行次数", stats.sync_runs ? "tone-ok" : "tone-warn"),
    miniCard("新增 / 更新", `${formatNumber(stats.inserted_items)} / ${formatNumber(stats.updated_items)}`, "新增条目与已有条目更新次数", stats.inserted_items || stats.updated_items ? "tone-ok" : "tone-warn"),
    miniCard("通知结果", `${formatNumber(stats.notifications_sent)} / ${formatNumber(stats.notifications_failed)}`, "成功 / 失败", stats.notifications_failed ? "tone-bad" : "tone-ok"),
  ].join("");
};

dashboard.renderRuntimeForm = function renderRuntimeForm() {
  const runtime = state.runtimeView;
  const values = runtime.values;
  qs("#runtime-summary-cards").innerHTML = [
    miniCard("微信地址", runtime.configured.wechat_push_url ? "已配置" : "未配置", values.wechat_push_url || "未填写推送地址", booleanTone(runtime.configured.wechat_push_url)),
    miniCard("微信令牌", runtime.configured.wechat_push_token ? "已配置" : "未配置", runtime.revealed ? (values.wechat_push_token || "未填写推送令牌") : "默认遮罩显示", booleanTone(runtime.configured.wechat_push_token)),
    miniCard("目标标识", runtime.configured.wechat_target_id ? "已配置" : "未配置", runtime.revealed ? (values.wechat_target_id || "未填写目标标识") : "默认遮罩显示", booleanTone(runtime.configured.wechat_target_id)),
    miniCard("豆瓣登录态", yesNo(runtime.configured.douban_cookie), runtime.revealed ? (values.douban_cookie || "未填写") : "默认遮罩显示", booleanTone(runtime.configured.douban_cookie)),
    miniCard("SMZDM 登录态", yesNo(runtime.configured.smzdm_cookie), runtime.revealed ? (values.smzdm_cookie || "未填写") : "默认遮罩显示", booleanTone(runtime.configured.smzdm_cookie)),
  ].join("");
  qs("#runtime_wechat_push_url").value = values.wechat_push_url || "";
  qs("#runtime_wechat_push_token").value = values.wechat_push_token || "";
  qs("#runtime_wechat_target_id").value = values.wechat_target_id || "";
  qs("#runtime_douban_cookie").value = values.douban_cookie || "";
  qs("#runtime_smzdm_cookie").value = values.smzdm_cookie || "";
  qs("#runtime-reveal-button").textContent = runtime.revealed ? "隐藏敏感值" : "显示敏感值";
};

dashboard.toggleRuntimeReveal = async function toggleRuntimeReveal() {
  const reveal = !state.runtimeView.revealed;
  state.runtimeView = await fetchRuntimeConfigView(reveal);
  dashboard.renderRuntimeForm();
  setAction(reveal ? "已显示敏感值" : "已隐藏敏感值");
};

dashboard.buildRuntimeSavePayload = async function buildRuntimeSavePayload() {
  return buildRuntimePayload({
    currentView: state.runtimeView,
    values: {
      wechat_push_url: qs("#runtime_wechat_push_url").value,
      douban_cookie: qs("#runtime_douban_cookie").value,
      smzdm_cookie: qs("#runtime_smzdm_cookie").value,
      wechat_push_token: qs("#runtime_wechat_push_token").value,
      wechat_target_id: qs("#runtime_wechat_target_id").value,
    },
  });
};
