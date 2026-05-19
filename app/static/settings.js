import { buildRuntimePayload, fetchRuntimeConfigView } from "./shared/runtime-config.js";

const form = document.getElementById("settings-form");
const statusNode = document.getElementById("status");
const reloadButton = document.getElementById("reload-button");
const revealButton = document.getElementById("reveal-button");
let currentView = null;

async function loadConfig(reveal = false) {
  statusNode.textContent = "读取中...";
  currentView = await fetchRuntimeConfigView(reveal);
  form.wechat_push_url.value = currentView.values.wechat_push_url || "";
  form.douban_cookie.value = currentView.values.douban_cookie || "";
  form.smzdm_cookie.value = currentView.values.smzdm_cookie || "";
  form.wechat_push_token.value = currentView.values.wechat_push_token || "";
  form.wechat_target_id.value = currentView.values.wechat_target_id || "";
  revealButton.textContent = currentView.revealed ? "隐藏敏感值" : "显示敏感值";
  statusNode.textContent = "已加载";
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  statusNode.textContent = "保存中...";
  const payload = await buildRuntimePayload({
    currentView,
    values: {
      wechat_push_url: form.wechat_push_url.value,
      douban_cookie: form.douban_cookie.value,
      smzdm_cookie: form.smzdm_cookie.value,
      wechat_push_token: form.wechat_push_token.value,
      wechat_target_id: form.wechat_target_id.value,
    },
  });
  const response = await fetch("/api/v1/runtime-config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    statusNode.textContent = "保存失败";
    return;
  }
  statusNode.textContent = "已保存";
  await loadConfig(false);
});

reloadButton.addEventListener("click", () => {
  loadConfig(currentView?.revealed || false).catch(() => {
    statusNode.textContent = "读取失败";
  });
});

revealButton.addEventListener("click", () => {
  loadConfig(!currentView?.revealed).catch(() => {
    statusNode.textContent = "读取失败";
  });
});

loadConfig(false).catch(() => {
  statusNode.textContent = "读取失败";
});
