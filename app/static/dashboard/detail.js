import { dashboard } from "./core.js";

const {
  qsa,
  qs,
  state,
  decodeRecord,
  fetchJson,
  safeUrl,
  escapeAttr,
  escapeHtml,
  formatDate,
  formatNumber,
  externalLink,
  statusPill,
  STATUS_LABELS,
} = dashboard;

dashboard.bindRecordSelection = function bindRecordSelection() {
  qsa("[data-record]").forEach((node) => {
    node.addEventListener("click", async () => {
      state.recordDetail = decodeRecord(node.dataset.record);
      await dashboard.renderRecordDetail();
    });
  });
};

dashboard.renderRecordDetail = async function renderRecordDetail() {
  const detailNode = qs("#record-detail");
  if (!state.recordDetail) {
    detailNode.innerHTML = `
      <div class="detail-hero">
        <h3>详情面板</h3>
        <div class="muted">点击左侧或中间任意一条记录，这里会展开结构化详情、图片和通知历史。</div>
      </div>
      <div class="empty">当前还没有选中记录。</div>
    `;
    return;
  }

  const detail = state.recordDetail;
  if (detail.source_key && detail.external_id) {
    try {
      const bundle = await fetchJson(`/api/v1/items/${encodeURIComponent(detail.source_key)}/${encodeURIComponent(detail.external_id)}/detail-view`);
      const item = bundle.item;
      const detailBody = bundle.detail?.body_text || "";
      const images = (bundle.detail?.image_urls || []).map((url) => safeUrl(url)).filter(Boolean);
      const evaluations = bundle.evaluations || [];
      const notifications = bundle.notifications || [];
      const matchedEvaluations = evaluations.filter((entry) => entry.matched);
      const latestMatch = matchedEvaluations[0] || null;
      const latestNotification = notifications[0] || null;
      const imageGallery = images.length
        ? `<div class="detail-gallery">${images.map((url) => `<a href="${escapeAttr(url)}" target="_blank" rel="noreferrer"><img src="${escapeAttr(url)}" alt="detail image"></a>`).join("")}</div>`
        : '<div class="muted">暂无图片</div>';
      const evaluationTimeline = matchedEvaluations.length
        ? `<div class="timeline">${matchedEvaluations.map((entry) => `
            <div class="timeline-item">
              <div class="timeline-title">${escapeHtml(entry.rule_key)} · ${escapeHtml(entry.reason)}</div>
              <div class="timeline-meta">时间 ${escapeHtml(formatDate(entry.evaluated_at))} · 价格 ${escapeHtml(formatNumber(entry.used_price_amount))} · 规格 ${escapeHtml(formatNumber(entry.used_spec_grams))}</div>
            </div>`).join("")}</div>`
        : '<div class="muted">暂无命中评估记录</div>';
      const notificationTimeline = notifications.length
        ? `<div class="timeline">${notifications.map((entry) => `
            <div class="timeline-item">
              <div class="timeline-title">${escapeHtml(STATUS_LABELS[String(entry.status || "").toLowerCase()] || entry.status)}</div>
              <div class="timeline-meta">时间 ${escapeHtml(formatDate(entry.updated_at))} · 目标 ${escapeHtml(entry.target || "-")} · 规则 ${escapeHtml(entry.rule_key)}</div>
            </div>`).join("")}</div>`
        : '<div class="muted">暂无通知记录</div>';
      detailNode.innerHTML = `
        <div class="detail-hero">
          <h3>${escapeHtml(item.title)}</h3>
          <div class="muted">${escapeHtml(item.source_key)} · ${escapeHtml(item.external_id)}</div>
          <div class="inline-flags">
            ${statusPill(detail.status || item.source_type)}
            ${latestMatch ? statusPill("matched") : ""}
            ${bundle.muted ? statusPill("muted") : ""}
            ${latestNotification ? statusPill(latestNotification.status) : ""}
          </div>
        </div>
        <div class="detail-grid">
          <section class="detail-block">
            <h4>基础信息</h4>
            <div class="detail-kv">
              <div><strong>来源</strong>${escapeHtml(item.source_key)}</div>
              <div><strong>作者</strong>${escapeHtml(item.author_name || "-")}</div>
              <div><strong>回复</strong>${escapeHtml(formatNumber(item.reply_count))}</div>
              <div><strong>最近活跃</strong>${escapeHtml(item.last_active_text || "-")}</div>
              <div><strong>首次入库</strong>${escapeHtml(formatDate(item.first_seen_at))}</div>
              <div><strong>最近看到</strong>${escapeHtml(formatDate(item.last_seen_at))}</div>
              <div><strong>原链接</strong>${externalLink(item.url, "打开原帖")}</div>
            </div>
          </section>
          <section class="detail-block">
            <h4>命中概览</h4>
            <div class="detail-kv">
              <div><strong>规则</strong>${escapeHtml(latestMatch ? latestMatch.rule_key : "暂无命中")}</div>
              <div><strong>原因</strong>${escapeHtml(latestMatch ? latestMatch.reason : "暂无命中")}</div>
              <div><strong>价格</strong>${escapeHtml(latestMatch ? formatNumber(latestMatch.used_price_amount) : "-")}</div>
              <div><strong>规格</strong>${escapeHtml(latestMatch ? formatNumber(latestMatch.used_spec_grams) : "-")}</div>
              <div><strong>通知</strong>${escapeHtml(latestNotification ? (STATUS_LABELS[String(latestNotification.status || "").toLowerCase()] || latestNotification.status) : "暂无通知")}</div>
            </div>
          </section>
        </div>
        <section class="detail-body">
          <h4>正文摘要</h4>
          <div class="detail-pre">${escapeHtml(detailBody || "暂无正文详情")}</div>
        </section>
        <section class="detail-body">
          <h4>图片</h4>
          ${imageGallery}
        </section>
        <section class="detail-body">
          <h4>命中历史</h4>
          ${evaluationTimeline}
        </section>
        <section class="detail-body">
          <h4>通知历史</h4>
          ${notificationTimeline}
        </section>
      `;
      return;
    } catch (error) {
      detailNode.innerHTML = `<div class="empty">加载详情失败：${escapeHtml(error.message)}</div>`;
      return;
    }
  }

  detailNode.innerHTML = `
    <div class="detail-hero">
      <h3>记录详情</h3>
      <div class="muted">当前标签：${state.activeTab}</div>
    </div>
    <pre class="detail-pre">${escapeHtml(JSON.stringify(detail, null, 2))}</pre>
  `;
};
