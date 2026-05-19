export const RUNTIME_SENSITIVE_FIELDS = [
  "douban_cookie",
  "smzdm_cookie",
  "wechat_push_token",
  "wechat_target_id",
];

export async function fetchRuntimeConfigView(reveal = false) {
  const response = await fetch(`/api/v1/runtime-config?reveal=${reveal ? "true" : "false"}`, {
    cache: "no-store",
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || response.statusText);
  }
  return payload;
}

export async function buildRuntimePayload({ currentView, values }) {
  let fullView = currentView;
  if (!currentView.revealed) {
    fullView = await fetchRuntimeConfigView(true);
  }

  const payload = {
    wechat_push_url: String(values.wechat_push_url ?? "").trim(),
  };

  for (const field of RUNTIME_SENSITIVE_FIELDS) {
    const currentValue = String(values[field] ?? "");
    const maskedValue = currentView.values[field];
    payload[field] = (!currentView.revealed && currentValue === maskedValue)
      ? (fullView.values[field] || "")
      : currentValue;
  }

  return payload;
}
