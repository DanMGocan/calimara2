import { useCallback, useEffect, useState } from "react";
import { addAdminModerationWord, addAdminPlatformAllowedEmail, cancelAdminJob, cleanupAdminStorageObject, createAdminEmailCampaign, createAdminInvitations, deleteAdminContent, deleteAdminStorageObject, deleteAdminUser, deleteAdminModerationWord, deleteAdminPlatformAllowedEmail, fetchAdminAuditLog, fetchAdminContent, fetchAdminEmailCampaigns, fetchAdminIntegrations, fetchAdminJobs, fetchAdminModerationWords, fetchAdminOverview, fetchAdminPerformanceHistory, fetchAdminPerformanceLive, fetchAdminPlatformAccess, fetchAdminQaReport, fetchAdminSiteFeedback, fetchAdminSiteFeedbackThread, fetchAdminStorageObjects, fetchAdminUsers, moderateAdminContent, presignAdminStorageObject, previewAdminEmail, processAdminEmailOutbox, reactivateAdminUser, replyAdminSiteFeedback, resendAdminInvitation, retryAdminJob, revokeAdminInvitation, rollupAdminMetrics, sendAdminNotificationTestEmail, suspendAdminUser, updateAdminContent, updateAdminPlatformAccess, updateAdminSiteFeedback, updateAdminUserPremium, updateAdminUserRoles, adjustAdminUserGologani } from "../api/admin.js";
import { createAdminShopItem, fetchAdminGologaniRewards, fetchAdminShopItems, updateAdminGologaniReward, updateAdminShopItem } from "../api/economy.js";
import { fetchExtendedModerationStats, fetchModerationLogs, fetchModerationQueue, fetchModerationStats, fetchPendingModerationContent, fetchPostReports, moderateContent, reviewModerationLog, reviewPostReport } from "../api/moderation.js";
import { contentTypeLabel, decisionLabel, formatDateTime, formatGologani, formatNumber, formatScore, htmlToText, slotLabel } from "../app/format.js";
import { AuthRequired, PageShell, StatusPanel } from "../app/layout.jsx";
import { blogUrl, mainPath } from "../app/paths.js";
import { safeExternalUrl } from "../app/urls.js";

const PREMIUM_TIER_LABELS = {
  free: "Gratuit",
  trubadur: "Trubadur",
  cronicar: "Cronicar",
  rapsod: "Rapsod"
};
const SITE_FEEDBACK_KIND_LABELS = {
  feedback: "Feedback",
  bug: "Bug"
};
const SITE_FEEDBACK_STATUS_LABELS = {
  open: "Deschis",
  closed: "Închis"
};
const INVITATION_STATUS_LABELS = {
  pending: "În așteptare",
  accepted: "Acceptată",
  revoked: "Revocată",
  expired: "Expirată"
};
const INVITATION_EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const ADMIN_NAV_GROUPS = [
  {
    label: "Platformă",
    items: ["overview", "access", "users", "content", "submissions", "email"]
  },
  {
    label: "Moderare",
    items: ["pending", "flagged", "reports", "journal", "wordlist"]
  },
  {
    label: "Operațiuni",
    items: ["integrations", "economy", "artStyles", "premium", "storage", "performance", "jobs", "audit"]
  }
];

const ART_STYLE_BACKDROPS = [
  { key: "checker", label: "Carouri (transparent)" },
  { key: "paper", label: "Hârtie" },
  { key: "warm", label: "Hârtie caldă" },
  { key: "dark", label: "Închis" }
];

const ART_STYLE_MOCKUPS = [
  {
    id: "oil",
    code: "Varianta 01",
    name: "Ulei clasic (Clarobscur)",
    medium: "Pictură în ulei · Vechi Maeștri",
    imageUrl: "/assets/style-mockups/manuscript-oil.png",
    description: "Tușe bogate de ulei cu lumină caldă de lumânare, umbre adânci de umbră arsă, pergament patinat și panglică grena cu sigiliu de ceară. Atmosferă solemnă de muzeu literar."
  },
  {
    id: "ink-wash",
    code: "Varianta 02",
    name: "Tuș și laviu sepia",
    medium: "Peniță și laviu · Jurnal literar",
    imageUrl: "/assets/style-mockups/manuscript-ink-wash.png",
    description: "Hașuri fine în peniță și laviu de tuș sepia-grafit, cu un singur accent cald de teracotă (#b84a2a) pe sigiliu. Se integrează nativ în estetica monocromă a platformei Călimara."
  },
  {
    id: "watercolor",
    code: "Varianta 03",
    name: "Acuarelă botanică",
    medium: "Acuarelă translucidă · Ediție ilustrată",
    imageUrl: "/assets/style-mockups/manuscript-watercolor.png",
    description: "Straturi translucide de acuarelă pe hârtie cu granulație fină, tonuri de ocru, albastru-ardezie în umbre și ornament floral delicat. Aerisit, poetic și luminos."
  },
  {
    id: "gouache",
    code: "Varianta 04",
    name: "Guașă mată de atelier",
    medium: "Guașă opacă · Obiect de colecție",
    imageUrl: "/assets/style-mockups/manuscript-gouache.png",
    description: "Tușe ferme de guașă mată, inițială aurită, șnur de piele și cataramă de alamă. Siluetă foarte clară și lizibilă atât la dimensiune mare, cât și ca miniatură în magazin."
  }
];

const MODERATION_WORD_CATEGORIES = [
  { key: "profanity", label: "Limbaj vulgar și insulte", kicker: "limbaj vulgar" },
  { key: "hate_speech", label: "Discurs de ură", kicker: "discurs de ură" }
];

const DEFAULT_STORAGE_FILTERS = {
  prefix: "",
  q: "",
  status: "all"
};

function premiumTierLabel(tier) {
  return PREMIUM_TIER_LABELS[tier] || tier || PREMIUM_TIER_LABELS.free;
}

function parseInvitationEmails(value) {
  return String(value || "")
    .split(/[\s,;]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function invitationResultMessage(response) {
  return `Invitații: ${formatNumber(response.created_count || 0)} noi, ${formatNumber(response.updated_count || 0)} retrimise, ${formatNumber(response.skipped_count || 0)} omise.`;
}

function qaReportTitle(entry) {
  return entry.title || String(entry.message || "").split(/\r?\n/).find((line) => line.trim()) || "Raport QA";
}

function qaReportBody(entry) {
  const body = entry.body || "";
  if (body.trim()) return body;
  const lines = String(entry.message || "").split(/\r?\n/);
  return lines.slice(1).join("\n").trim() || entry.message || "";
}

const DEFAULT_USER_FILTERS = {
  role: "all",
  status: "all",
  premium: "all",
  joined_from: "",
  joined_to: "",
  last_login_from: "",
  last_login_to: "",
  min_posts: "",
  max_posts: ""
};

const DEFAULT_EMAIL_FILTERS = {
  ...DEFAULT_USER_FILTERS,
  q: "",
  status: "active"
};

function cleanFilters(filters) {
  return Object.fromEntries(
    Object.entries(filters).filter(([, value]) => value !== "" && value !== null && value !== undefined)
  );
}

function countActiveUserFilters(search, filters) {
  let count = search.trim() ? 1 : 0;
  if (filters.role !== DEFAULT_USER_FILTERS.role) count += 1;
  if (filters.status !== DEFAULT_USER_FILTERS.status) count += 1;
  if (filters.premium !== DEFAULT_USER_FILTERS.premium) count += 1;
  if (filters.joined_from || filters.joined_to) count += 1;
  if (filters.last_login_from || filters.last_login_to) count += 1;
  if (filters.min_posts || filters.max_posts) count += 1;
  return count;
}

function formatCornerBadge(count) {
  const value = Math.max(0, Number(count) || 0);
  return value > 99 ? "99+" : formatNumber(value);
}

function feedbackUnreadReplyLabel(count) {
  const value = Math.max(0, Number(count) || 0);
  if (value === 1) return "1 răspuns nou";
  return `${formatNumber(value)} răspunsuri noi`;
}

function normalizeAdminHref(value) {
  const raw = String(value || "").trim();
  if (!raw || raw === "#") return "";
  if (/^(https?:)?\/\//i.test(raw)) return raw;
  if (raw.startsWith("/")) return mainPath(raw);
  return raw;
}

function profileHref(username, explicitUrl = "") {
  const direct = normalizeAdminHref(explicitUrl);
  if (direct) return direct;
  const clean = String(username || "").trim().replace(/^@/, "");
  if (!clean || clean === "Necunoscut" || clean === "Anonim") return "";
  return blogUrl(clean);
}

function postHrefFromParts(author, slug, anchor = "") {
  const cleanAuthor = String(author || "").trim().replace(/^@/, "");
  const cleanSlug = String(slug || "").trim().replace(/^\/+/, "");
  if (!cleanAuthor || !cleanSlug) return "";
  const hash = anchor ? `#${String(anchor).replace(/^#/, "")}` : "";
  return `${blogUrl(cleanAuthor)}/${cleanSlug}${hash}`;
}

function contentHref(item = {}) {
  if (!item) return "";
  if (item.type === "post" && item.author && item.slug) return postHrefFromParts(item.author, item.slug);
  if (item.type === "comment" && item.post_author && item.post_slug) {
    return postHrefFromParts(item.post_author, item.post_slug, `comment-${item.id}`);
  }
  if (item.type === "audio" && item.post_author && item.post_slug) return postHrefFromParts(item.post_author, item.post_slug);
  if (item.type === "forum_thread" && item.slug) return mainPath(`/discutii/${item.slug}`);
  if (item.type === "forum_reply" && item.thread_slug) return mainPath(`/discutii/${item.thread_slug}#reply-${item.id}`);
  if (item.type === "theatre_entry" && item.play_slug) return mainPath(`/teatru/${item.play_slug}`);
  if (item.type === "stafeta_segment" && item.work_slug) return mainPath(`/stafeta/${item.work_slug}`);
  return normalizeAdminHref(item.target_url);
}

function reportHref(report = {}) {
  if (report.post_author && report.post_slug && report.target_type === "post") {
    return postHrefFromParts(report.post_author, report.post_slug);
  }
  return normalizeAdminHref(report.target_url || report.post_url);
}

function AdminTextLink({ href, children, className = "admin-inline-link" }) {
  const normalized = normalizeAdminHref(href);
  if (!normalized) return children ?? null;
  return <a className={className} href={normalized}>{children}</a>;
}

function AdminPreview({ children, href }) {
  if (!children) return null;
  const normalized = normalizeAdminHref(href);
  if (normalized) return <a className="admin-preview admin-preview-link" href={normalized}>{children}</a>;
  return <p className="admin-preview">{children}</p>;
}

function AdminStat({ label, value, sub }) {
  const displayValue = typeof value === "number" ? formatNumber(value) : (value ?? 0);
  return (
    <div className="admin-stat">
      <span className="admin-stat-line">
        <span className="admin-stat-label">{label}:</span>{" "}
        <strong className="admin-stat-value">{displayValue}</strong>
        {sub ? <span className="admin-stat-sub"> ({sub})</span> : null}
      </span>
    </div>
  );
}
function AdminStatGrid({ children, compact = false }) {
  return <div className={compact ? "admin-mini-grid" : "admin-stat-grid"}>{children}</div>;
}
function AdminWorkRow({ item, mode, busy, onApprove, onReject }) {
  const [rejectReason, setRejectReason] = useState("");
  const isFlagged = mode === "flagged";
  const content = isFlagged ? item.content : item;
  const contentType = isFlagged ? item.content_type : item.type;
  const itemId = isFlagged ? item.log_id : `${contentType}:${item.id}`;
  const title = content?.title || content?.post_title || contentTypeLabel(contentType);
  const preview = content?.content || item.content || "";
  const author = content?.author || item.author || "Necunoscut";
  const targetHref = contentHref(content);
  const authorHref = profileHref(author, content?.author_url || item.author_url);
  const createdAt = content?.created_at || item.created_at || item.flagged_at;
  const score = isFlagged ? item.ai_analysis?.toxicity_score : item.toxicity_score;
  const reason = isFlagged ? item.ai_analysis?.reason : item.moderation_reason;
  const status = isFlagged ? item.ai_analysis?.decision : item.moderation_status;
  const approveBusy = busy === `${mode}:${itemId}:approve`;
  const rejectBusy = busy === `${mode}:${itemId}:reject`;

  const submitReject = () => {
    const reasonText = rejectReason.trim();
    if (!reasonText) return;
    onReject(item, reasonText);
  };

  return (
    <article className="admin-row">
      <div className="admin-row-head">
        <div>
          <div className="admin-badges">
            <span className="piece-card-status">{contentTypeLabel(contentType)}</span>
            {status ? <span className="piece-card-status status-flagged">{decisionLabel(status)}</span> : null}
            {score !== null && score !== undefined ? <span className="piece-card-status">{formatScore(score)}</span> : null}
          </div>
          <h2 className="admin-row-title">
            <AdminTextLink className="admin-title-link" href={targetHref}>{title}</AdminTextLink>
          </h2>
        </div>
        <div className="admin-row-meta">
          <span><AdminTextLink href={authorHref}>{author}</AdminTextLink></span>
          {createdAt ? <span>{formatDateTime(createdAt)}</span> : null}
        </div>
      </div>
      {preview || reason ? (
        <div className="admin-row-body">
          {preview ? <AdminPreview href={targetHref}>{htmlToText(preview)}</AdminPreview> : null}
          {reason ? <p className="admin-reason">{reason}</p> : null}
        </div>
      ) : null}
      <div className="admin-actions">
        <button className="cal-btn primary" type="button" disabled={Boolean(busy)} onClick={() => onApprove(item)}>
          {approveBusy ? "Se aprobă..." : "Aprobă"}
        </button>
        <div className="admin-reject-row">
          <input
            className="cal-input"
            value={rejectReason}
            onChange={(event) => setRejectReason(event.target.value)}
            placeholder="Motiv respingere"
            aria-label="Motiv respingere"
          />
          <button className="cal-btn" type="button" disabled={Boolean(busy) || !rejectReason.trim()} onClick={submitReject}>
            {rejectBusy ? "Se respinge..." : "Respinge"}
          </button>
        </div>
      </div>
    </article>
  );
}
function AdminJournalRow({ log }) {
  const targetHref = normalizeAdminHref(log.target_url);
  const authorHref = profileHref(log.content_author, log.content_author_url);
  const moderatorHref = profileHref(log.moderator, log.moderator_url);
  return (
    <article className="admin-row">
      <div className="admin-row-head">
        <div>
          <div className="admin-badges">
            <span className="piece-card-status">{contentTypeLabel(log.content_type)}</span>
            <span className="piece-card-status status-flagged">AI: {decisionLabel(log.ai_decision)}</span>
            <span className="piece-card-status">Om: {decisionLabel(log.human_decision)}</span>
            {log.needs_review ? <span className="piece-card-status status-rejected">revizie</span> : null}
          </div>
          <h2 className="admin-row-title">
            <AdminTextLink className="admin-title-link" href={targetHref}>{log.content_title || contentTypeLabel(log.content_type)}</AdminTextLink>
          </h2>
        </div>
        <div className="admin-row-meta">
          {log.content_author ? <span><AdminTextLink href={authorHref}>{log.content_author}</AdminTextLink></span> : null}
          {log.created_at ? <span>{formatDateTime(log.created_at)}</span> : null}
        </div>
      </div>
      <div className="admin-row-body">
        {log.content_preview ? <AdminPreview href={targetHref}>{htmlToText(log.content_preview)}</AdminPreview> : null}
        <div className="admin-journal-grid">
          <span>toxicitate {formatScore(log.toxicity_score)}</span>
          {log.moderator ? <span>moderator <AdminTextLink href={moderatorHref}>{log.moderator}</AdminTextLink></span> : null}
          {log.moderated_at ? <span>moderat {formatDateTime(log.moderated_at)}</span> : null}
        </div>
        {log.ai_reason ? <p className="admin-reason">{log.ai_reason}</p> : null}
        {log.human_reason ? <p className="admin-reason">{log.human_reason}</p> : null}
      </div>
    </article>
  );
}
function reportTypeLabel(type) {
  if (type === "offensive") return "Conținut ofensiv";
  if (type === "plagiarism") return "Plagiat";
  return type || "Raportare";
}
function AdminReportRow({ report, busy, onDismiss, onRejectPost, onDeletePost }) {
  const reportBusy = busy?.startsWith(`report:${report.id}:`);
  const evidence = report.evidence_url ? String(report.evidence_url) : "";
  const details = report.details ? String(report.details) : "";
  const targetUrl = reportHref(report);
  const authorHref = profileHref(report.post_author, report.post_author_url);
  const reporterHref = profileHref(report.reporter_username, report.reporter_url);
  const reviewerHref = profileHref(report.reviewer_username, report.reviewer_url);
  const title = report.post_title || "Postare ștearsă";
  const targetLabel = report.target_label || "Postare";
  return (
    <article className="admin-row">
      <div className="admin-row-head">
        <div>
          <div className="admin-badges">
            <span className="piece-card-status">{targetLabel}</span>
            <span className="piece-card-status">{reportTypeLabel(report.reason_type)}</span>
            <span className="piece-card-status">{decisionLabel(report.status)}</span>
          </div>
          <h2 className="admin-row-title">
            <AdminTextLink className="admin-title-link" href={targetUrl}>{title}</AdminTextLink>
          </h2>
        </div>
        <div className="admin-row-meta">
          {report.post_author ? <span><AdminTextLink href={authorHref}>{report.post_author}</AdminTextLink></span> : null}
          {report.created_at ? <span>{formatDateTime(report.created_at)}</span> : null}
        </div>
      </div>
      <div className="admin-row-body">
        {details ? <AdminPreview href={targetUrl}>{details}</AdminPreview> : null}
        {targetUrl ? <p className="admin-reason"><a href={targetUrl}>Deschide conținutul raportat</a></p> : null}
        {evidence ? <p className="admin-reason">{evidence}</p> : null}
        <div className="admin-journal-grid">
          {report.reporter_username ? <span>raportat de <AdminTextLink href={reporterHref}>{report.reporter_username}</AdminTextLink></span> : null}
          {report.reviewer_username ? <span>revizuit de <AdminTextLink href={reviewerHref}>{report.reviewer_username}</AdminTextLink></span> : null}
          {report.reviewed_at ? <span>{formatDateTime(report.reviewed_at)}</span> : null}
        </div>
        {report.review_note ? <p className="admin-reason">{report.review_note}</p> : null}
      </div>
      {report.status === "open" ? (
        <div className="admin-actions">
          <button className="cal-btn" type="button" disabled={Boolean(reportBusy)} onClick={() => onDismiss(report)}>Închide raportarea</button>
          <button className="cal-btn" type="button" disabled={Boolean(reportBusy) || !report.post_id} onClick={() => onRejectPost(report)}>Respinge postarea</button>
          <button className="cal-btn danger" type="button" disabled={Boolean(reportBusy) || !report.post_id} onClick={() => onDeletePost(report)}>Șterge postarea</button>
        </div>
      ) : null}
    </article>
  );
}
function AdminPanel({ title, description, children, actions }) {
  return (
    <section className="admin-panel">
      <div className="admin-panel-head">
        <div className="admin-panel-title-group">
          <h2>{title}</h2>
          {description ? <p>{description}</p> : null}
        </div>
        {actions ? <div className="admin-panel-actions">{actions}</div> : null}
      </div>
      {children}
    </section>
  );
}
function adminPrompt(label, fallback = "") {
  const value = window.prompt(label, fallback);
  if (value === null) return null;
  const trimmed = value.trim();
  return trimmed || null;
}
function adminReason(label = "Motiv administrativ") {
  return adminPrompt(label);
}
function formatBytes(value) {
  const bytes = Number(value ?? 0);
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const amount = bytes / (1024 ** index);
  return `${amount.toLocaleString("ro-RO", { maximumFractionDigits: index ? 1 : 0 })} ${units[index]}`;
}
function formatPercent(value) {
  const amount = Number(value ?? 0);
  if (!Number.isFinite(amount)) return "0%";
  return `${amount.toLocaleString("ro-RO", { maximumFractionDigits: 1 })}%`;
}
function formatDuration(value) {
  const seconds = Math.max(0, Number(value || 0));
  if (!Number.isFinite(seconds) || seconds <= 0) return "0s";
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days) return `${days}z ${hours}h`;
  if (hours) return `${hours}h ${minutes}m`;
  if (minutes) return `${minutes}m`;
  return `${Math.floor(seconds)}s`;
}
function statusCount(summary = {}, status) {
  return Number(summary.by_status?.[status] || summary[status] || 0);
}
function AdminKeyValueGrid({ items }) {
  return (
    <div className="admin-performance-kv-grid">
      {items.map((item) => (
        <div className="admin-performance-kv" key={item.label}>
          <span>{item.label}</span>
          <strong>{item.value}</strong>
          {item.sub ? <em>{item.sub}</em> : null}
        </div>
      ))}
    </div>
  );
}
function AdminPerformanceProcessTable({ processes = [] }) {
  if (!processes.length) return <StatusPanel title="Nu am găsit workere active" />;
  return (
    <div className="admin-performance-table-wrap">
      <table className="admin-performance-table">
        <thead>
          <tr>
            <th>Rol</th>
            <th>PID</th>
            <th>Status</th>
            <th>CPU</th>
            <th>RAM</th>
            <th>Uptime</th>
            <th>Comandă</th>
          </tr>
        </thead>
        <tbody>
          {processes.map((process) => (
            <tr key={`${process.role}-${process.pid}`}>
              <td>{process.role}</td>
              <td>{process.pid}</td>
              <td>{process.status}</td>
              <td>{formatPercent(process.cpu_percent)}</td>
              <td>{formatBytes(process.rss_bytes)}</td>
              <td>{formatDuration(process.uptime_seconds)}</td>
              <td><span className="admin-performance-command">{process.command || process.name}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function AdminPerformanceHistory({ points = [] }) {
  if (!points.length) return <StatusPanel title="Istoricul se va popula după primul minut" />;
  const visiblePoints = points.slice(-24);
  return (
    <div className="admin-performance-history" aria-label="Istoric performanță">
      {visiblePoints.map((point, index) => {
        const metrics = point.metrics || {};
        const cpu = Number(metrics.host?.cpu_percent || 0);
        const ram = Number(metrics.host?.memory?.used_percent || 0);
        const label = point.captured_at ? formatDateTime(point.captured_at) : `Punct ${index + 1}`;
        return (
          <div className="admin-performance-history-point" key={`${point.captured_at || index}-${index}`} title={`${label}: CPU ${formatPercent(cpu)}, RAM ${formatPercent(ram)}`}>
            <span className="admin-performance-bar cpu" style={{ height: `${Math.max(4, Math.min(100, cpu))}%` }} />
            <span className="admin-performance-bar ram" style={{ height: `${Math.max(4, Math.min(100, ram))}%` }} />
          </div>
        );
      })}
    </div>
  );
}
function AdminDataRow({ kicker, badges = [], title, titleHref, meta, preview, previewHref, children, compact = false, className = "" }) {
  const extraClass = className ? ` ${className}` : "";
  return (
    <article className={`admin-row${compact ? " compact" : ""}${extraClass}`}>
      <div className="admin-row-head">
        <div>
          <div className="admin-badges">
            {kicker ? <span className="piece-card-status">{kicker}</span> : null}
            {badges.map((badge, index) => (
              <span className={`piece-card-status ${badge.className || ""}`.trim()} key={`${badge.label}-${index}`}>
                {badge.label}
              </span>
            ))}
          </div>
          <h2 className="admin-row-title">
            <AdminTextLink className="admin-title-link" href={titleHref}>{title}</AdminTextLink>
          </h2>
        </div>
        {meta ? <div className="admin-row-meta">{meta}</div> : null}
      </div>
      {preview ? <div className="admin-row-body"><AdminPreview href={previewHref}>{preview}</AdminPreview></div> : null}
      {children ? <div className="admin-actions">{children}</div> : null}
    </article>
  );
}
function AdminQaReportRow({ entry }) {
  const pageUrl = safeExternalUrl(entry.page_url);
  const stamp = entry.report_stamp || entry.client_context?.report_stamp;
  const part = entry.report_part || entry.client_context?.part;
  return (
    <article className="admin-row admin-report-row">
      <div className="admin-row-head">
        <div>
          <div className="admin-badges">
            <span className="piece-card-status">Raport QA · {SITE_FEEDBACK_STATUS_LABELS[entry.status] || entry.status}</span>
            {stamp ? <span className="piece-card-status">{stamp}</span> : null}
            {part ? <span className="piece-card-status">{part}</span> : null}
          </div>
          <h2 className="admin-row-title">{qaReportTitle(entry)}</h2>
        </div>
        <div className="admin-row-meta">
          <span>#{entry.id}</span>
          <span>{formatDateTime(entry.created_at)}</span>
        </div>
      </div>
      <div className="admin-row-body">
        <p className="admin-report-body">{qaReportBody(entry)}</p>
      </div>
      {pageUrl ? (
        <div className="admin-actions">
          <a className="cal-btn" href={pageUrl} target="_blank" rel="noreferrer">Pagina testată</a>
        </div>
      ) : null}
    </article>
  );
}
function SiteFeedbackReplyModal({ state, busy, onReplyChange, onClose, onSend }) {
  if (!state.open) return null;
  const feedback = state.thread?.feedback || state.item || {};
  const messages = state.thread?.messages || [];
  return (
    <div className="admin-feedback-reply-scrim" role="presentation" onClick={onClose}>
      <section className="admin-feedback-reply-modal" role="dialog" aria-modal="true" aria-labelledby="admin-feedback-reply-title" onClick={(event) => event.stopPropagation()}>
        <button className="feedback-modal-close" type="button" aria-label="Închide" onClick={onClose} disabled={Boolean(busy)}>x</button>
        <header className="admin-feedback-reply-head">
          <div>
            <span className="piece-card-status">{SITE_FEEDBACK_KIND_LABELS[feedback.kind] || feedback.kind || "Sesizare"}</span>
            <h2 id="admin-feedback-reply-title" className="admin-feedback-reply-title">Răspuns către {feedback.username_snapshot || `utilizator #${feedback.user_id || "n/a"}`}</h2>
          </div>
          <div className="admin-row-meta">
            {feedback.support_conversation_id ? <span>Conversație #{feedback.support_conversation_id}</span> : <span>Conversație nouă</span>}
            {feedback.created_at ? <span>{formatDateTime(feedback.created_at)}</span> : null}
          </div>
        </header>
        <div className="admin-feedback-original">
          <strong>Sesizare</strong>
          <p>{feedback.message}</p>
          {feedback.page_url ? <a href={safeExternalUrl(feedback.page_url)} target="_blank" rel="noreferrer">Pagina trimisă</a> : null}
        </div>
        {state.loading ? <div className="message-thread-note">Se încarcă firul...</div> : null}
        {state.error ? <div className="inline-error">{state.error}</div> : null}
        <div className="admin-feedback-thread" aria-live="polite">
          {messages.map((message) => (
            <div className={`admin-feedback-message ${message.sender_is_system ? "system" : "user"}`} key={message.id}>
              <div className="admin-feedback-message-head">
                <strong>{message.sender_label || message.sender_username || "Utilizator"}</strong>
                <time dateTime={message.created_at}>{formatDateTime(message.created_at)}</time>
              </div>
              <p>{message.content}</p>
            </div>
          ))}
          {!state.loading && !messages.length ? <div className="message-thread-note">Firul se va crea la primul răspuns.</div> : null}
        </div>
        <form className="admin-feedback-reply-form" onSubmit={onSend}>
          <label className="cal-label" htmlFor="admin-feedback-reply-content">Răspuns</label>
          <textarea
            id="admin-feedback-reply-content"
            className="cal-textarea admin-feedback-reply-textarea"
            value={state.reply}
            onChange={(event) => onReplyChange(event.target.value)}
            maxLength="2000"
            rows="5"
            autoFocus
          />
          <div className="feedback-form-foot">
            <span className="feedback-counter">{state.reply.trim().length}/2000</span>
            <div className="admin-actions inline">
              <button className="cal-btn" type="button" onClick={onClose} disabled={Boolean(busy)}>Anulează</button>
              <button className="cal-btn primary" type="submit" disabled={Boolean(busy) || !state.reply.trim()}>{busy ? "Se trimite..." : "Trimite răspuns"}</button>
            </div>
          </div>
        </form>
      </section>
    </div>
  );
}
const INTEGRATION_STATUS_LABELS = {
  active: { label: "✓ Complet", className: "status-ok" },
  ready: { label: "Configurat, oprit", className: "status-pending" },
  incomplete: { label: "Incomplet", className: "status-rejected" },
  not_configured: { label: "Neconfigurat", className: "status-pending" }
};
function AdminIntegrationRow({ item }) {
  const status = INTEGRATION_STATUS_LABELS[item.status] || INTEGRATION_STATUS_LABELS.not_configured;
  return (
    <article className={`admin-row admin-integration${item.status === "active" ? " is-complete" : ""}`}>
      <div className="admin-row-head">
        <div>
          <div className="admin-badges">
            <span className={`piece-card-status ${status.className}`}>{status.label}</span>
          </div>
          <h2 className="admin-row-title">{item.name}</h2>
          <p className="admin-integration-purpose">{item.purpose}</p>
        </div>
      </div>
      <div className="admin-integration-body">
        <div className="admin-integration-vars">
          <h3>Variabile în .env</h3>
          <ul>
            {item.env.map((variable) => (
              <li key={variable.name}>
                <span className={`piece-card-status ${variable.is_set ? "status-ok" : variable.required ? "status-rejected" : "status-pending"}`}>
                  {variable.is_set ? "setat" : variable.required ? "lipsește" : "opțional"}
                </span>
                <code>{variable.name}</code>
                <em>{variable.hint}</em>
              </li>
            ))}
            {item.flags.map((flag) => (
              <li key={flag.name}>
                <span className={`piece-card-status ${flag.enabled ? "status-ok" : "status-pending"}`}>{flag.enabled ? "pornit" : "oprit"}</span>
                <code>{flag.name}</code>
                <em>comutator: True / False</em>
              </li>
            ))}
            {item.backends.map((backend) => (
              <li key={backend.name}>
                <span className={`piece-card-status ${backend.value === "s3" ? "status-ok" : "status-pending"}`}>{backend.value}</span>
                <code>{backend.name}</code>
                <em>local sau s3</em>
              </li>
            ))}
            {item.backup ? (
              <li>
                <span className={`piece-card-status ${item.backup.ok ? "status-ok" : "status-rejected"}`}>{item.backup.ok ? "backup reușit" : "backup eșuat"}</span>
                <code>{formatDateTime(item.backup.at)}</code>
                <em>{item.backup.ok ? `${Math.round((item.backup.size_bytes || 0) / 1024)} KB · ${item.backup.kept} copii păstrate` : item.backup.error}</em>
              </li>
            ) : null}
            {item.credentials_file ? (
              <li>
                <span className={`piece-card-status ${item.credentials_file.exists ? "status-ok" : "status-rejected"}`}>{item.credentials_file.exists ? "fișier găsit" : "fișier lipsă"}</span>
                <code>{item.credentials_file.name}</code>
                <em>fișierul JSON al contului de serviciu</em>
              </li>
            ) : null}
          </ul>
        </div>
        <div className="admin-integration-steps">
          <h3>Pași</h3>
          <ol>
            {item.steps.map((step, index) => <li key={index}>{step}</li>)}
          </ol>
          {item.notes.length ? (
            <ul className="admin-integration-notes">
              {item.notes.map((note, index) => <li key={index}>{note}</li>)}
            </ul>
          ) : null}
        </div>
      </div>
    </article>
  );
}
function AdminStorageRow({ object, busy, onPreview, onDelete, onCleanup }) {
  const references = object.references || [];
  const meta = (
    <>
      <span>{formatBytes(object.size)}</span>
      {object.last_modified ? <span>{formatDateTime(object.last_modified)}</span> : null}
      <span>{object.prefix_type === "outside" ? "extern" : object.prefix_type}</span>
    </>
  );
  const preview = references.length
    ? references.map((reference, index) => (
      <span className="admin-reference-item" key={`${reference.type}-${reference.id}-${index}`}>
        {index ? <span className="admin-reference-separator"> · </span> : null}
        <AdminTextLink href={reference.target_url}>{reference.label}</AdminTextLink>
      </span>
    ))
    : object.protected_reason || "Fără referință în baza de date.";
  return (
    <AdminDataRow
      compact
      kicker={`${object.can_delete ? "ștergibil" : "protejat"} · ${references.length ? "referențiat" : "nereferențiat"}`}
      title={object.key}
      meta={meta}
      preview={preview}
    >
      <button className="cal-btn" type="button" disabled={Boolean(busy)} onClick={() => onPreview(object)}>Deschide</button>
      <button className="cal-btn danger" type="button" disabled={Boolean(busy) || !object.can_delete} title={object.protected_reason || ""} onClick={() => onDelete(object)}>
        Șterge
      </button>
      <button className="cal-btn danger" type="button" disabled={Boolean(busy)} onClick={() => onCleanup(object)}>
        Curăță
      </button>
    </AdminDataRow>
  );
}
function AdminDashboardView({ user }) {
  const canAdmin = Boolean(user?.is_admin);
  const canModerate = Boolean(user?.is_admin || user?.is_moderator);
  const [activeTab, setActiveTab] = useState(canAdmin ? "overview" : "pending");
  const [styleBackdrop, setStyleBackdrop] = useState("checker");
  const [userSearch, setUserSearch] = useState("");
  const [userFilters, setUserFilters] = useState(DEFAULT_USER_FILTERS);
  const [userFiltersOpen, setUserFiltersOpen] = useState(false);
  const [accessEmail, setAccessEmail] = useState("");
  const [accessNote, setAccessNote] = useState("");
  const [moderationWord, setModerationWord] = useState("");
  const [moderationWordCategory, setModerationWordCategory] = useState("profanity");
  const [inviteEmails, setInviteEmails] = useState("");
  const [inviteTier, setInviteTier] = useState("free");
  const [inviteDays, setInviteDays] = useState("30");
  const [inviteNote, setInviteNote] = useState("");
  const [inviteStatus, setInviteStatus] = useState({ kind: "", message: "" });
  const [contentSearch, setContentSearch] = useState("");
  const [contentType, setContentType] = useState("all");
  const [feedbackKind, setFeedbackKind] = useState("all");
  const [feedbackStatus, setFeedbackStatus] = useState("open");
  const [storageFilters, setStorageFilters] = useState(DEFAULT_STORAGE_FILTERS);
  const [selectedUserIds, setSelectedUserIds] = useState(() => new Set());
  const [emailFilters, setEmailFilters] = useState(DEFAULT_EMAIL_FILTERS);
  const [emailMode, setEmailMode] = useState("filters");
  const [emailSubject, setEmailSubject] = useState("");
  const [emailHtml, setEmailHtml] = useState("<p>Bună,</p>\n<p></p>");
  const [emailPreview, setEmailPreview] = useState(null);
  const [state, setState] = useState({
    overview: null,
    stats: null,
    extendedStats: null,
    pending: [],
    flagged: [],
    postReports: [],
    logs: [],
    users: [],
    content: [],
    platformAccess: null,
    jobs: [],
    audit: [],
    shop: [],
    gologaniRewards: [],
    qaReport: [],
    qaReportTotal: 0,
    qaReportOpenCount: 0,
    qaReportClosedCount: 0,
    submissions: [],
    submissionsTotal: 0,
    submissionsUnreadReplyCount: 0,
    emailCampaigns: [],
    error: "",
    loading: true
  });
  const [storageState, setStorageState] = useState({
    objects: [],
    nextCursor: null,
    summary: null,
    loading: false,
    error: "",
    loaded: false
  });
  const [integrationsState, setIntegrationsState] = useState({
    data: null,
    loading: false,
    error: "",
    loaded: false
  });
  const [performanceState, setPerformanceState] = useState({
    live: null,
    history: [],
    historyAvailable: false,
    loading: false,
    error: "",
    loaded: false,
    updatedAt: ""
  });
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");
  const [feedbackReplyState, setFeedbackReplyState] = useState({
    open: false,
    item: null,
    thread: null,
    reply: "",
    loading: false,
    error: ""
  });

  const loadAdminData = useCallback(async () => {
    if (!canModerate) {
      setState((current) => ({ ...current, loading: false }));
      return;
    }
    setState((current) => ({ ...current, loading: true, error: "" }));
    try {
      const [stats, extendedStats, pending, flagged, reports, logs] = await Promise.all([
        fetchModerationStats(),
        fetchExtendedModerationStats(),
        fetchPendingModerationContent(),
        fetchModerationQueue(),
        fetchPostReports({ status: "open", limit: 50 }),
        fetchModerationLogs({ limit: 100 })
      ]);
      let adminData = {
        overview: null,
        users: [],
        content: [],
        platformAccess: null,
        moderationWords: null,
        jobs: [],
        audit: [],
        shop: [],
        gologaniRewards: [],
        qaReport: [],
        qaReportTotal: 0,
        qaReportOpenCount: 0,
        qaReportClosedCount: 0,
        submissions: [],
        submissionsTotal: 0,
        submissionsUnreadReplyCount: 0
      };
      if (canAdmin) {
        const [overview, users, content, platformAccess, moderationWords, jobs, audit, shop, gologaniRewards, qaReport, submissions, emailCampaigns] = await Promise.all([
          fetchAdminOverview(),
          fetchAdminUsers({ q: userSearch, ...cleanFilters(userFilters), limit: 50 }),
          fetchAdminContent({ q: contentSearch, content_type: contentType, limit: 50 }),
          fetchAdminPlatformAccess(),
          fetchAdminModerationWords(),
          fetchAdminJobs({ limit: 50 }),
          fetchAdminAuditLog({ limit: 100 }),
          fetchAdminShopItems(),
          fetchAdminGologaniRewards(),
          fetchAdminQaReport({ limit: 200 }),
          fetchAdminSiteFeedback({ kind: feedbackKind, status: feedbackStatus, limit: 50 }),
          fetchAdminEmailCampaigns({ limit: 20 })
        ]);
        adminData = {
          overview,
          users: users.users || [],
          content: content.content || [],
          platformAccess,
          moderationWords,
          jobs: jobs.jobs || [],
          audit: audit.logs || [],
          shop: Array.isArray(shop) ? shop : [],
          gologaniRewards: Array.isArray(gologaniRewards) ? gologaniRewards : [],
          qaReport: qaReport.entries || [],
          qaReportTotal: qaReport.total || 0,
          qaReportOpenCount: qaReport.open_count || 0,
          qaReportClosedCount: qaReport.closed_count || 0,
          submissions: submissions.submissions || [],
          submissionsTotal: submissions.total || 0,
          submissionsUnreadReplyCount: submissions.unread_reply_count || 0,
          emailCampaigns: emailCampaigns.campaigns || []
        };
      }
      setState({
        stats,
        extendedStats,
        pending: pending.content || [],
        flagged: flagged.queue || [],
        postReports: reports.reports || [],
        logs: logs.logs || [],
        ...adminData,
        error: "",
        loading: false
      });
    } catch (requestError) {
      setState((current) => ({
        ...current,
        error: requestError.message || "Nu am putut încărca adminul.",
        loading: false
      }));
    }
  }, [canAdmin, canModerate, contentSearch, contentType, feedbackKind, feedbackStatus, userFilters, userSearch]);

  useEffect(() => {
    loadAdminData();
  }, [loadAdminData]);

  const loadStorageObjects = useCallback(async ({ cursor = "", append = false } = {}) => {
    if (!canAdmin) return;
    setStorageState((current) => ({ ...current, loading: true, error: "" }));
    try {
      const response = await fetchAdminStorageObjects({
        ...cleanFilters(storageFilters),
        limit: 50,
        cursor
      });
      setStorageState((current) => ({
        objects: append ? [...current.objects, ...(response.objects || [])] : (response.objects || []),
        nextCursor: response.next_cursor || null,
        summary: response.summary || null,
        loading: false,
        error: "",
        loaded: true
      }));
    } catch (requestError) {
      setStorageState((current) => ({
        ...current,
        loading: false,
        error: requestError.message || "Nu am putut încărca obiectele din bucket.",
        loaded: true
      }));
    }
  }, [canAdmin, storageFilters]);

  useEffect(() => {
    if (canAdmin && activeTab === "storage" && !storageState.loaded && !storageState.loading) {
      loadStorageObjects();
    }
  }, [activeTab, canAdmin, loadStorageObjects, storageState.loaded, storageState.loading]);

  const loadIntegrations = useCallback(async () => {
    if (!canAdmin) return;
    setIntegrationsState((current) => ({ ...current, loading: true, error: "" }));
    try {
      const data = await fetchAdminIntegrations();
      setIntegrationsState({ data, loading: false, error: "", loaded: true });
    } catch (requestError) {
      setIntegrationsState((current) => ({
        ...current,
        loading: false,
        error: requestError.message || "Nu am putut încărca integrările.",
        loaded: true
      }));
    }
  }, [canAdmin]);

  useEffect(() => {
    if (canAdmin && activeTab === "integrations" && !integrationsState.loaded && !integrationsState.loading) {
      loadIntegrations();
    }
  }, [activeTab, canAdmin, loadIntegrations, integrationsState.loaded, integrationsState.loading]);

  const loadPerformanceData = useCallback(async ({ quiet = false } = {}) => {
    if (!canAdmin) return;
    if (!quiet) {
      setPerformanceState((current) => ({ ...current, loading: true, error: "" }));
    }
    try {
      const [live, history] = await Promise.all([
        fetchAdminPerformanceLive(),
        fetchAdminPerformanceHistory({ hours: 24 })
      ]);
      setPerformanceState({
        live,
        history: history.points || [],
        historyAvailable: Boolean(history.available),
        loading: false,
        error: "",
        loaded: true,
        updatedAt: live.captured_at || new Date().toISOString()
      });
    } catch (requestError) {
      setPerformanceState((current) => ({
        ...current,
        loading: false,
        error: requestError.message || "Nu am putut încărca performanța platformei.",
        loaded: true
      }));
    }
  }, [canAdmin]);

  useEffect(() => {
    if (!canAdmin || activeTab !== "performance") return undefined;
    loadPerformanceData();
    const timerId = window.setInterval(() => loadPerformanceData({ quiet: true }), 10000);
    return () => window.clearInterval(timerId);
  }, [activeTab, canAdmin, loadPerformanceData]);

  if (!user) return <AuthRequired />;
  if (!canModerate) {
    return <PageShell kicker="admin" title="Acces refuzat" sub="Contul curent nu are drepturi de moderare." />;
  }

  const runAction = async (key, action) => {
    setBusy(key);
    setStatus("");
    try {
      await action();
      setStatus("Acțiunea a fost salvată.");
      await loadAdminData();
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut salva acțiunea.");
    } finally {
      setBusy("");
    }
  };

  const approvePending = (item) => runAction(
    `pending:${item.type}:${item.id}:approve`,
    () => moderateContent(item.type, item.id, { action: "approve", reason: "Aprobat din panoul de administrare" })
  );
  const rejectPending = (item, reason) => runAction(
    `pending:${item.type}:${item.id}:reject`,
    () => moderateContent(item.type, item.id, { action: "reject", reason })
  );
  const approveFlagged = (item) => runAction(
    `flagged:${item.log_id}:approve`,
    () => reviewModerationLog(item.log_id, { action: "approved", reason: "Aprobat din panoul de administrare" })
  );
  const rejectFlagged = (item, reason) => runAction(
    `flagged:${item.log_id}:reject`,
    () => reviewModerationLog(item.log_id, { action: "rejected", reason })
  );
  const dismissReport = (report) => {
    const reason = adminReason("Motiv închidere raportare");
    if (!reason) return;
    runAction(`report:${report.id}:dismiss`, () => reviewPostReport(report.id, { action: "dismiss", reason }));
  };
  const rejectReportedPost = (report) => {
    const reason = adminReason("Motiv respingere postare");
    if (!reason) return;
    runAction(`report:${report.id}:reject`, () => reviewPostReport(report.id, { action: "reject_post", reason }));
  };
  const deleteReportedPost = (report) => {
    if (!window.confirm(`Ștergi definitiv postarea raportată "${report.post_title || report.post_id}"?`)) return;
    const reason = adminReason("Motiv ștergere postare");
    if (!reason) return;
    runAction(`report:${report.id}:delete`, () => reviewPostReport(report.id, { action: "delete_post", reason }));
  };

  const changeRoles = (target, next) => {
    const reason = adminReason("Motiv schimbare roluri");
    if (!reason) return;
    runAction(`user:${target.id}:roles`, () => updateAdminUserRoles(target.id, { ...next, reason }));
  };
  const suspendTarget = (target) => {
    const reason = adminReason("Motiv suspendare");
    if (!reason) return;
    runAction(`user:${target.id}:suspend`, () => suspendAdminUser(target.id, reason));
  };
  const reactivateTarget = (target) => {
    const reason = adminReason("Motiv reactivare");
    if (!reason) return;
    runAction(`user:${target.id}:reactivate`, () => reactivateAdminUser(target.id, reason));
  };
  const premiumTarget = (target) => {
    const tier = adminPrompt("Tier premium: free, trubadur, cronicar, rapsod", target.premium_tier || "free");
    if (!tier) return;
    const reason = adminReason("Motiv modificare premium");
    if (!reason) return;
    const days = tier === "free" ? 0 : Number(adminPrompt("Valabilitate în zile", "30") || 30);
    const premiumUntil = tier === "free" ? null : new Date(Date.now() + Math.max(days, 1) * 86400000).toISOString();
    runAction(`user:${target.id}:premium`, () => updateAdminUserPremium(target.id, { premium_tier: tier, premium_until: premiumUntil, reason }));
  };
  const adjustCoins = (target) => {
    const amount = Number(adminPrompt("Ajustare Gologani (+/-)", "25"));
    if (!Number.isFinite(amount) || amount === 0) return;
    const reason = adminReason("Motiv ajustare Gologani");
    if (!reason) return;
    runAction(`user:${target.id}:coins`, () => adjustAdminUserGologani(target.id, { amount, reason }));
  };
  const deleteTarget = (target) => {
    if (!window.confirm(`Ștergi definitiv utilizatorul ${target.username}?`)) return;
    const reason = adminReason("Motiv ștergere definitivă");
    if (!reason) return;
    runAction(`user:${target.id}:delete`, () => deleteAdminUser(target.id, reason));
  };
  const setUserFilter = (field, value) => {
    setUserFilters((current) => ({ ...current, [field]: value }));
  };
  const setEmailFilter = (field, value) => {
    setEmailFilters((current) => ({ ...current, [field]: value }));
    setEmailPreview(null);
  };
  const toggleSelectedUser = (target, checked) => {
    setSelectedUserIds((current) => {
      const next = new Set(current);
      if (checked) next.add(target.id);
      else next.delete(target.id);
      return next;
    });
  };
  const emailSelectedUsers = () => {
    if (!selectedUserIds.size) return;
    setEmailMode("selected");
    setActiveTab("email");
    setEmailPreview(null);
  };
  const emailAudiencePayload = () => (
    emailMode === "selected"
      ? { selected_user_ids: [...selectedUserIds] }
      : { ...cleanFilters(emailFilters), selected_user_ids: [] }
  );
  const previewEmailAudience = async () => {
    setBusy("email:preview");
    setStatus("");
    try {
      const response = await previewAdminEmail({ audience: emailAudiencePayload() });
      setEmailPreview(response);
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut calcula destinatarii.");
    } finally {
      setBusy("");
    }
  };
  const sendAdminEmail = async () => {
    if (!emailSubject.trim() || !htmlToText(emailHtml).trim()) {
      setStatus("Completează subiectul și conținutul HTML.");
      return;
    }
    setBusy("email:send");
    setStatus("");
    try {
      const response = await createAdminEmailCampaign({
        audience: emailAudiencePayload(),
        subject: emailSubject.trim(),
        html_content: emailHtml
      });
      setStatus(`Campania a fost pusă în coadă: ${formatNumber(response.queued_count)} emailuri.`);
      setEmailPreview(null);
      await loadAdminData();
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut pune campania în coadă.");
    } finally {
      setBusy("");
    }
  };
  const processEmailOutbox = async () => {
    setBusy("email:process");
    setStatus("");
    try {
      const response = await processAdminEmailOutbox({ limit: 50 });
      setStatus(`Coada email a procesat ${formatNumber(response.processed)} intrări. Rămase: ${formatNumber(response.pending_count)}.`);
      await loadAdminData();
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut procesa coada email.");
    } finally {
      setBusy("");
    }
  };
  const sendNotificationTestEmail = async () => {
    setBusy("email:test-notification");
    setStatus("");
    try {
      const response = await sendAdminNotificationTestEmail();
      const delivery = response.sent ? "trimis" : "pus în coadă";
      setStatus(`Mostra de notificare pentru utilizatori a fost ${delivery} către ${response.recipient_email}. Status: ${response.status}.`);
      await loadAdminData();
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut trimite emailul de test pentru notificări.");
    } finally {
      setBusy("");
    }
  };
  const setPlatformOpen = (nextOpen) => {
    runAction(`platform-access:${nextOpen ? "open" : "closed"}`, () => updateAdminPlatformAccess({ open: nextOpen }));
  };
  const addPlatformEmail = async (event) => {
    event.preventDefault();
    const email = accessEmail.trim();
    if (!email) return;
    setBusy("platform-access:add");
    setStatus("");
    try {
      await addAdminPlatformAllowedEmail({ email, note: accessNote.trim() || null });
      setAccessEmail("");
      setAccessNote("");
      setStatus("Emailul a fost adăugat în lista de acces.");
      await loadAdminData();
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut adăuga emailul.");
    } finally {
      setBusy("");
    }
  };
  const updateInviteEmails = (value) => {
    setInviteEmails(value);
    if (inviteStatus.message) {
      setInviteStatus({ kind: "", message: "" });
    }
  };
  const sendInvitations = async (event) => {
    event.preventDefault();
    const emails = parseInvitationEmails(inviteEmails);
    if (!emails.length) {
      setInviteStatus({ kind: "error", message: "Adaugă cel puțin un email pentru invitație." });
      return;
    }
    const invalidEmail = emails.find((email) => !INVITATION_EMAIL_PATTERN.test(email));
    if (invalidEmail) {
      setInviteStatus({ kind: "error", message: `Email invalid: ${invalidEmail}. Separă adresele cu virgulă, punct și virgulă sau rând nou.` });
      return;
    }
    const premiumDays = inviteTier === "free" ? null : Number(inviteDays || 30);
    if (inviteTier !== "free" && (!Number.isFinite(premiumDays) || premiumDays < 1 || premiumDays > 3650)) {
      setInviteStatus({ kind: "error", message: "Zilele premium trebuie să fie între 1 și 3650." });
      return;
    }
    setBusy("platform-invitations:add");
    setStatus("");
    setInviteStatus({ kind: "info", message: "Se trimit invitațiile..." });
    try {
      const response = await createAdminInvitations({
        emails,
        premium_tier: inviteTier,
        premium_days: premiumDays,
        note: inviteNote.trim() || null
      });
      const message = invitationResultMessage(response);
      setInviteEmails("");
      setInviteNote("");
      setInviteStatus({ kind: "success", message });
      await loadAdminData();
    } catch (requestError) {
      setInviteStatus({ kind: "error", message: requestError.message || "Nu am putut trimite invitațiile." });
    } finally {
      setBusy("");
    }
  };
  const addModerationWord = async (event) => {
    event.preventDefault();
    const word = moderationWord.trim();
    if (!word) return;
    setBusy("moderation-word:add");
    setStatus("");
    try {
      await addAdminModerationWord({ word, category: moderationWordCategory });
      setModerationWord("");
      setStatus(`„${word}” a fost adăugat în lista de cuvinte filtrate.`);
      await loadAdminData();
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut adăuga cuvântul.");
    } finally {
      setBusy("");
    }
  };
  const removeModerationWord = (item) => {
    if (!window.confirm(`Scoți „${item.word}” din lista de cuvinte filtrate?`)) return;
    runAction(`moderation-word:${item.id}:delete`, () => deleteAdminModerationWord(item.id));
  };
  const removePlatformEmail = (item) => {
    if (!window.confirm(`Ștergi ${item.email} din lista de acces?`)) return;
    runAction(`platform-access:${item.id}:delete`, () => deleteAdminPlatformAllowedEmail(item.id));
  };
  const resendInvitation = (item) => {
    runAction(`platform-invitation:${item.id}:resend`, () => resendAdminInvitation(item.id));
  };
  const revokeInvitation = (item) => {
    if (!window.confirm(`Revoci invitația pentru ${item.email}?`)) return;
    runAction(`platform-invitation:${item.id}:revoke`, () => revokeAdminInvitation(item.id));
  };

  const moderateListedContent = (item, action) => {
    const reason = action === "approve" ? "Aprobat din panoul de administrare" : adminReason("Motiv acțiune conținut");
    if (!reason) return;
    runAction(`content:${item.type}:${item.id}:${action}`, () => moderateAdminContent(item.type, item.id, { action, reason }));
  };
  const flagListedContent = (item) => {
    const reason = adminReason("Motiv marcare conținut");
    if (!reason) return;
    runAction(`content:${item.type}:${item.id}:flag`, () => updateAdminContent(item.type, item.id, { moderation_status: "flagged", reason }));
  };
  const editContentTitle = (item) => {
    const title = adminPrompt("Titlu nou", item.title || "");
    if (!title) return;
    const reason = adminReason("Motiv editare conținut");
    if (!reason) return;
    runAction(`content:${item.type}:${item.id}:title`, () => updateAdminContent(item.type, item.id, { title, reason }));
  };
  const deleteListedContent = (item) => {
    if (!window.confirm(`Ștergi definitiv ${contentTypeLabel(item.type)} #${item.id}?`)) return;
    const reason = adminReason("Motiv ștergere conținut");
    if (!reason) return;
    runAction(`content:${item.type}:${item.id}:delete`, () => deleteAdminContent(item.type, item.id, reason));
  };

  const retryJob = (job) => {
    const reason = adminReason("Motiv retry job");
    if (!reason) return;
    runAction(`job:${job.id}:retry`, () => retryAdminJob(job.id, reason));
  };
  const cancelJob = (job) => {
    const reason = adminReason("Motiv anulare job");
    if (!reason) return;
    runAction(`job:${job.id}:cancel`, () => cancelAdminJob(job.id, reason));
  };

  const createShopItem = () => {
    const slug = adminPrompt("Slug obiect magazin");
    const name = slug ? adminPrompt("Nume obiect") : null;
    const price = name ? Number(adminPrompt("Preț", "25")) : NaN;
    const slot = Number.isFinite(price) ? adminPrompt("Slot: profile_badge, costume, frame, background, title", "profile_badge") : null;
    if (!slug || !name || !slot || !Number.isFinite(price)) return;
    runAction("shop:create", () => createAdminShopItem({ slug, name, price, slot }));
  };
  const toggleShopItem = (item) => runAction(`shop:${item.id}:toggle`, () => updateAdminShopItem(item.id, { is_active: !item.is_active }));
  const repriceShopItem = (item) => {
    const price = Number(adminPrompt("Preț nou", String(item.price ?? 0)));
    if (!Number.isFinite(price)) return;
    runAction(`shop:${item.id}:price`, () => updateAdminShopItem(item.id, { price }));
  };
  const updateGologaniRewardAmount = (reward) => {
    const amount = Number(adminPrompt("Gologani pentru interacțiune", String(reward.amount ?? 0)));
    if (!Number.isFinite(amount) || amount < 0) return;
    runAction(`gologani-reward:${reward.event_type}:amount`, () => updateAdminGologaniReward(reward.event_type, { amount }));
  };
  const toggleGologaniReward = (reward) => {
    runAction(
      `gologani-reward:${reward.event_type}:toggle`,
      () => updateAdminGologaniReward(reward.event_type, { is_active: !reward.is_active })
    );
  };

  const runRollup = () => {
    const date = adminPrompt("Dată pentru metricile zilnice YYYY-MM-DD, gol pentru ieri", "");
    runAction("metrics:rollup", () => rollupAdminMetrics(date || undefined));
  };

  const changeFeedbackStatus = (item, nextStatus) => {
    const note = window.prompt("Notă admin (opțional)", item.admin_note || "");
    if (note === null) return;
    runAction(
      `site-feedback:${item.id}:${nextStatus}`,
      () => updateAdminSiteFeedback(item.id, { status: nextStatus, admin_note: note.trim() || null })
    );
  };
  const openFeedbackReply = async (item) => {
    setFeedbackReplyState({ open: true, item, thread: null, reply: "", loading: true, error: "" });
    try {
      const thread = await fetchAdminSiteFeedbackThread(item.id);
      setFeedbackReplyState((current) => ({ ...current, thread, loading: false, error: "" }));
      setState((current) => ({
        ...current,
        submissions: current.submissions.map((submission) => submission.id === thread.feedback.id ? thread.feedback : submission),
        submissionsUnreadReplyCount: thread.unread_reply_count || 0
      }));
    } catch (requestError) {
      setFeedbackReplyState((current) => ({
        ...current,
        loading: false,
        error: requestError.message || "Nu am putut încărca firul de suport."
      }));
    }
  };
  const closeFeedbackReply = () => {
    if (busy === "site-feedback:reply") return;
    setFeedbackReplyState({ open: false, item: null, thread: null, reply: "", loading: false, error: "" });
  };
  const sendFeedbackReply = async (event) => {
    event.preventDefault();
    const feedbackId = feedbackReplyState.thread?.feedback?.id || feedbackReplyState.item?.id;
    const content = feedbackReplyState.reply.trim();
    if (!feedbackId || !content || busy) return;
    setBusy("site-feedback:reply");
    setStatus("");
    try {
      const thread = await replyAdminSiteFeedback(feedbackId, { content });
      setFeedbackReplyState((current) => ({ ...current, thread, item: thread.feedback, reply: "", loading: false, error: "" }));
      setState((current) => ({
        ...current,
        submissions: current.submissions.map((item) => item.id === thread.feedback.id ? thread.feedback : item),
        submissionsUnreadReplyCount: thread.unread_reply_count || 0
      }));
      setStatus("Răspunsul a fost trimis ca mesaj direct de la Călimara.");
    } catch (requestError) {
      setFeedbackReplyState((current) => ({
        ...current,
        error: requestError.message || "Nu am putut trimite răspunsul."
      }));
    } finally {
      setBusy("");
    }
  };
  const setStorageFilter = (field, value) => {
    setStorageFilters((current) => ({ ...current, [field]: value }));
    setStorageState((current) => ({ ...current, nextCursor: null }));
  };
  const applyStorageFilters = (event) => {
    event.preventDefault();
    loadStorageObjects();
  };
  const refreshStorageObjects = () => {
    loadStorageObjects();
  };
  const loadMoreStorageObjects = () => {
    if (!storageState.nextCursor) return;
    loadStorageObjects({ cursor: storageState.nextCursor, append: true });
  };
  const previewStorageObject = async (object) => {
    setBusy(`storage:${object.key}:preview`);
    setStatus("");
    try {
      const response = await presignAdminStorageObject(object.key);
      window.open(response.url, "_blank", "noreferrer");
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut deschide obiectul.");
    } finally {
      setBusy("");
    }
  };
  const deleteStorageObject = (object) => {
    if (!object.can_delete) return;
    if (!window.confirm(`Ștergi definitiv obiectul "${object.key}" din bucket?`)) return;
    const reason = adminReason("Motiv ștergere obiect");
    if (!reason) return;
    runAction(`storage:${object.key}:delete`, async () => {
      await deleteAdminStorageObject(object.key, reason);
      await loadStorageObjects();
    });
  };
  const cleanupStorageObject = async (object) => {
    const references = object.references?.length || 0;
    const referenceText = references
      ? ` Va elimina ${formatNumber(references)} referințe cunoscute din baza de date.`
      : " Nu există referințe cunoscute în baza de date.";
    if (!window.confirm(`Cureți definitiv obiectul "${object.key}" din bucket?${referenceText}`)) return;
    const reason = adminReason("Motiv curățare obiect");
    if (!reason) return;
    setBusy(`storage:${object.key}:cleanup`);
    setStatus("");
    try {
      const response = await cleanupAdminStorageObject(object.key, reason);
      setStatus(`Obiect curățat. Referințe eliminate: ${formatNumber(response.references_removed || 0)}.`);
      await loadStorageObjects();
      await loadAdminData();
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut curăța obiectul.");
    } finally {
      setBusy("");
    }
  };

  const tabs = canAdmin
    ? [
        ["overview", "Ansamblu", state.overview?.cards?.pending_moderation],
        ["access", "Acces", (state.platformAccess?.allowed_count || 0) + (state.platformAccess?.invitation_count || 0)],
        ["users", "Utilizatori", state.users.length],
        ["content", "Conținut", state.content.length],
        ["submissions", "Sesizări", state.submissionsTotal],
        ["email", "Email", state.emailCampaigns.length],
        ["pending", "Moderare", state.pending.length + state.flagged.length],
        ["reports", "Raportări", state.postReports.length],
        ["journal", "Jurnal", state.logs.length],
        ["wordlist", "Cuvinte filtrate", state.moderationWords?.count || 0],
        ["integrations", "Integrări", integrationsState.data?.summary?.incomplete || 0],
        ["economy", "Economie", state.shop.length],
        ["artStyles", "Stil vizual", ART_STYLE_MOCKUPS.length],
        ["premium", "Premium", state.overview?.cards?.active_premium_users],
        ["storage", "Stocare", storageState.objects.length],
        ["performance", "Performanță", performanceState.live?.processes?.workers?.length || 0],
        ["jobs", "Joburi", state.jobs.length],
        ["audit", "Audit", state.audit.length]
      ]
    : [
        ["pending", "În așteptare AI", state.pending.length],
        ["flagged", "Marcate", state.flagged.length],
        ["reports", "Raportări", state.postReports.length],
        ["journal", "Jurnal", state.logs.length]
      ];
  const tabsByKey = Object.fromEntries(tabs.map((tab) => [tab[0], tab]));
  const navGroups = ADMIN_NAV_GROUPS
    .map((group) => ({
      ...group,
      tabs: group.items.map((key) => tabsByKey[key]).filter(Boolean)
    }))
    .filter((group) => group.tabs.length);

  const cards = state.overview?.cards || {};
  const premiumByTier = state.overview?.premium?.by_tier || {};
  const jobsByStatus = state.overview?.jobs?.by_status || {};
  const traffic = state.overview?.traffic || {};
  const activeUserFilterCount = countActiveUserFilters(userSearch, userFilters);
  const unreadFeedbackReplyCount = Math.max(0, Number(state.submissionsUnreadReplyCount) || 0);
  const platformAccess = state.platformAccess || { open: false, allowed_count: 0, emails: [], invitation_count: 0, invitations: [] };
  const inviteBusy = busy === "platform-invitations:add";
  const moderationWords = state.moderationWords || { available: true, count: 0, words: [] };
  const performanceLive = performanceState.live || {};
  const performanceHost = performanceLive.host || {};
  const performanceDatabase = performanceLive.database || {};
  const performanceProcesses = performanceLive.processes || {};
  const performanceQueues = performanceLive.queues || {};
  const performanceUsers = performanceLive.users || {};
  const performanceRuntime = performanceLive.runtime || {};
  const performanceWorkers = performanceProcesses.workers || [];
  const databaseConnections = performanceDatabase.connections || {};

  return (
    <PageShell kicker="admin" title={canAdmin ? "Admin" : "Moderare"} sub={`Conectat ca ${user.username}.`}>
      <div className="admin-workspace">
        <section className="admin-summary" aria-label="Rezumat admin">
          <AdminStatGrid>
            <AdminStat label="Utilizatori" value={canAdmin ? cards.total_users : state.stats?.pending_count} sub={canAdmin ? `${formatNumber(cards.new_users)} noi` : "în coadă"} />
            <AdminStat label="Conținut" value={canAdmin ? cards.total_posts : state.stats?.flagged_count} sub={canAdmin ? `${formatNumber(cards.pending_moderation)} pending` : "marcate"} />
            <AdminStat label="Vizualizări" value={canAdmin ? traffic.unique_views : state.stats?.today_actions} sub={canAdmin ? "reale" : "decizii azi"} />
            <AdminStat label="Premium" value={canAdmin ? cards.active_premium_users : state.extendedStats?.total_logs} sub={canAdmin ? "active" : "jurnal"} />
            <AdminStat label="Joburi" value={canAdmin ? cards.failed_jobs : state.extendedStats?.pending_review_count} sub={canAdmin ? "eșuate" : "revizie"} />
          </AdminStatGrid>
        </section>

        <nav className="admin-nav" aria-label="Admin">
          {navGroups.map((group) => (
            <section className="admin-nav-group" key={group.label}>
              <h2>{group.label}</h2>
              <div className="admin-tabs" role="tablist" aria-label={group.label}>
                {group.tabs.map(([key, label, count]) => {
                  const alertCount = key === "submissions" ? unreadFeedbackReplyCount : 0;
                  return (
                    <button key={key} className={`admin-tab ${activeTab === key ? "active" : ""}`} type="button" role="tab" aria-selected={activeTab === key} onClick={() => setActiveTab(key)}>
                      <span>{label}</span>
                      <strong>{formatNumber(count || 0)}</strong>
                      {alertCount > 0 ? (
                        <span className="admin-tab-alert-badge" aria-label={`${formatNumber(alertCount)} răspunsuri noi la sesizări`}>
                          {formatCornerBadge(alertCount)}
                        </span>
                      ) : null}
                    </button>
                  );
                })}
              </div>
            </section>
          ))}
          {canAdmin ? (
            <section className="admin-nav-group">
              <h2>Referință</h2>
              <div className="admin-tabs">
                <button className={`admin-tab ${activeTab === "qaReport" ? "active" : ""}`} type="button" role="tab" aria-selected={activeTab === "qaReport"} onClick={() => setActiveTab("qaReport")}>
                  <span>Raport QA</span>
                  <strong>{formatNumber(state.qaReportTotal || 0)}</strong>
                </button>
                <a className="admin-tab admin-tab-link" href="/docs">
                  <span>Documentație</span>
                  <strong>docs</strong>
                </a>
              </div>
            </section>
          ) : null}
        </nav>

        <div className="admin-status-stack">
          {state.loading ? <StatusPanel title="Se încarcă" /> : null}
          {state.error ? <StatusPanel title="Nu am putut încărca adminul">{state.error}</StatusPanel> : null}
          {status ? <div className="inline-error">{status}</div> : null}
        </div>

      {!state.loading && !state.error && canAdmin && activeTab === "overview" ? (
        <div className="admin-grid">
          <AdminPanel
            title="Operațiuni"
            description="Indicatori operaționali și mentenanță."
            actions={(
              <div className="admin-rollup-action">
                <span>Recalculează metricile zilnice.</span>
                <button className="cal-btn" type="button" disabled={Boolean(busy)} onClick={runRollup}>Actualizează metrici</button>
              </div>
            )}
          >
            <AdminStatGrid compact>
              <AdminStat label="Comentarii" value={cards.total_comments} sub={`${formatNumber(cards.new_comments)} noi`} />
              <AdminStat label="Suspendați" value={cards.suspended_users} sub="conturi" />
              <AdminStat label="Marcate" value={cards.flagged_moderation} sub="moderare" />
              <AdminStat label="Magazin" value={cards.shop_items} sub="obiecte" />
            </AdminStatGrid>
          </AdminPanel>
          <AdminPanel title="Trafic" description="Vizualizări totale, reale și automate.">
            <AdminStatGrid compact>
              <AdminStat label="Total" value={traffic.total_views} sub="views" />
              <AdminStat label="Reale" value={traffic.unique_views} sub="dedup" />
              <AdminStat label="Boți" value={traffic.bot_views} sub={`${traffic.bot_percentage || 0}%`} />
            </AdminStatGrid>
          </AdminPanel>
        </div>
      ) : null}

      {!state.loading && !state.error && canAdmin && activeTab === "wordlist" ? (
        <div className="admin-grid">
          <AdminPanel title="Cuvinte filtrate" description="Orice text care conține unul dintre aceste cuvinte sau expresii ajunge direct la revizie manuală, fără verificarea AI de context literar. Potrivirea se face pe cuvinte întregi, fără diferență între majuscule și minuscule; formele cu și fără diacritice se adaugă separat. Modificările se aplică imediat conținutului nou.">
            {moderationWords.available ? (
              <form className="admin-access-form" onSubmit={addModerationWord}>
                <input className="cal-input" value={moderationWord} onChange={(event) => setModerationWord(event.target.value)} placeholder="Cuvânt sau expresie" maxLength="100" required />
                <select className="cal-input" value={moderationWordCategory} onChange={(event) => setModerationWordCategory(event.target.value)}>
                  {MODERATION_WORD_CATEGORIES.map((category) => <option key={category.key} value={category.key}>{category.label}</option>)}
                </select>
                <button className="cal-btn primary" type="submit" disabled={Boolean(busy) || !moderationWord.trim()}>{busy === "moderation-word:add" ? "Se adaugă..." : "Adaugă"}</button>
              </form>
            ) : (
              <StatusPanel title="Lista nu poate fi editată încă">Tabelul moderation_words lipsește din baza de date. Până la rularea migrării, moderarea folosește lista implicită din cod.</StatusPanel>
            )}
          </AdminPanel>
          {moderationWords.available ? MODERATION_WORD_CATEGORIES.map((category) => {
            const words = (moderationWords.words || []).filter((item) => item.category === category.key);
            return (
              <AdminPanel key={category.key} title={category.label} description={`${formatNumber(words.length)} cuvinte.`}>
                {words.length ? (
                  <ul className="admin-word-chips">
                    {words.map((item) => (
                      <li key={item.id} className="admin-word-chip">
                        <span>{item.word}</span>
                        <button type="button" disabled={Boolean(busy)} onClick={() => removeModerationWord(item)} aria-label={`Scoate ${item.word} din listă`} title="Scoate din listă">×</button>
                      </li>
                    ))}
                  </ul>
                ) : <StatusPanel title={`Niciun cuvânt la „${category.kicker}”`} />}
              </AdminPanel>
            );
          }) : null}
        </div>
      ) : null}

      {!state.loading && !state.error && canAdmin && activeTab === "access" ? (
        <div className="admin-grid">
          <AdminPanel title="Acces platformă" description="Platforma pornește închisă; doar emailurile permise pot intra până este deschisă manual.">
            <div className="admin-access-status">
              <div>
                <span className="rail-label">Stare</span>
                <strong>OPEN={platformAccess.open ? "true" : "false"}</strong>
                <p>{platformAccess.open ? "Orice email poate folosi autentificarea și înregistrarea." : "Doar emailurile din lista de acces pot folosi autentificarea și înregistrarea."}</p>
              </div>
              <button className="cal-btn primary" type="button" disabled={Boolean(busy)} onClick={() => setPlatformOpen(!platformAccess.open)}>
                {platformAccess.open ? "Închide accesul" : "Deschide platforma"}
              </button>
            </div>
          </AdminPanel>
          <AdminPanel title="Emailuri permise" description={`${formatNumber(platformAccess.allowed_count)} adrese în lista de acces.`}>
            <form className="admin-access-form" onSubmit={addPlatformEmail}>
              <input className="cal-input" type="email" value={accessEmail} onChange={(event) => setAccessEmail(event.target.value)} placeholder="email@example.com" required />
              <input className="cal-input" value={accessNote} onChange={(event) => setAccessNote(event.target.value)} placeholder="Notă opțională" maxLength="500" />
              <button className="cal-btn primary" type="submit" disabled={Boolean(busy) || !accessEmail.trim()}>{busy === "platform-access:add" ? "Se adaugă..." : "Adaugă"}</button>
            </form>
            <div className="admin-feed compact">
              {platformAccess.emails?.length ? platformAccess.emails.map((item) => (
                <AdminDataRow
                  key={item.id}
                  compact
                  kicker="email permis"
                  title={item.email}
                  meta={<span>{formatDateTime(item.created_at)}</span>}
                  preview={item.note || ""}
                >
                  <button className="cal-btn danger" type="button" disabled={Boolean(busy)} onClick={() => removePlatformEmail(item)}>Șterge</button>
                </AdminDataRow>
              )) : <StatusPanel title="Lista de acces este goală" />}
            </div>
          </AdminPanel>
          <AdminPanel title="Invitații" description={`${formatNumber(platformAccess.invitation_count || 0)} invitații create. Emailurile invitate pot intra cât timp platforma este închisă.`}>
            <form className="admin-invite-form" onSubmit={sendInvitations} noValidate>
              <textarea className="cal-input admin-invite-emails" value={inviteEmails} onChange={(event) => updateInviteEmails(event.target.value)} placeholder="email1@example.com, email2@example.com" aria-describedby="admin-invite-status" required />
              <div className="admin-controls admin-filter-controls">
                <select className="cal-input" value={inviteTier} onChange={(event) => setInviteTier(event.target.value)}>
                  <option value="free">Gratuit</option>
                  <option value="trubadur">Trubadur</option>
                  <option value="cronicar">Cronicar</option>
                  <option value="rapsod">Rapsod</option>
                </select>
                <input className="cal-input compact-number" type="number" min="1" max="3650" value={inviteDays} onChange={(event) => setInviteDays(event.target.value)} placeholder="Zile premium" disabled={inviteTier === "free"} />
                <input className="cal-input" value={inviteNote} onChange={(event) => setInviteNote(event.target.value)} placeholder="Notă opțională" maxLength="500" />
                <button className="cal-btn primary" type="submit" disabled={Boolean(busy) || !inviteEmails.trim()}>{inviteBusy ? "Se trimit..." : "Trimite invitații"}</button>
              </div>
              {inviteStatus.message ? (
                <div id="admin-invite-status" className={inviteStatus.kind === "success" || inviteStatus.kind === "info" ? "inline-status admin-invite-status" : "inline-error admin-invite-status"} role={inviteStatus.kind === "error" ? "alert" : "status"} aria-live="polite">
                  {inviteStatus.message}
                </div>
              ) : null}
            </form>
            <div className="admin-feed compact">
              {platformAccess.invitations?.length ? platformAccess.invitations.map((item) => (
                <AdminDataRow
                  key={item.id}
                  compact
                  kicker={`invitație · ${INVITATION_STATUS_LABELS[item.status] || item.status}`}
                  title={item.email}
                  meta={<><span>{premiumTierLabel(item.premium_tier)}{item.premium_tier !== "free" ? ` · ${formatNumber(item.premium_days || 30)} zile` : ""}</span><span>{formatDateTime(item.created_at)}</span></>}
                  preview={item.note || (item.expires_at ? `Expiră: ${formatDateTime(item.expires_at)}` : "")}
                >
                  {item.status !== "accepted" ? <button className="cal-btn" type="button" disabled={Boolean(busy)} onClick={() => resendInvitation(item)}>Retrimite</button> : null}
                  {item.status === "pending" || item.status === "expired" ? <button className="cal-btn danger" type="button" disabled={Boolean(busy)} onClick={() => revokeInvitation(item)}>Revocă</button> : null}
                </AdminDataRow>
              )) : <StatusPanel title="Nu există invitații" />}
            </div>
          </AdminPanel>
        </div>
      ) : null}

      {!state.loading && !state.error && canAdmin && activeTab === "users" ? (
        <AdminPanel
          title="Utilizatori"
          description="Conturi, roluri, premium și suspendări."
          actions={(
            <div className="admin-controls">
              <button className="cal-btn" type="button" aria-expanded={userFiltersOpen} onClick={() => setUserFiltersOpen((open) => !open)}>
                {userFiltersOpen ? "Ascunde filtre" : `Filtre${activeUserFilterCount ? ` (${formatNumber(activeUserFilterCount)})` : ""}`}
              </button>
              <button className="cal-btn" type="button" disabled={!selectedUserIds.size} onClick={emailSelectedUsers}>Email selectați</button>
            </div>
          )}
        >
          {userFiltersOpen ? (
            <div className="admin-filter-panel">
              <label className="admin-filter-field wide">
                <span>Caută</span>
                <input className="cal-input admin-search" value={userSearch} onChange={(event) => setUserSearch(event.target.value)} placeholder="username sau email" />
              </label>
              <label className="admin-filter-field">
                <span>Rol</span>
                <select className="cal-input" value={userFilters.role} onChange={(event) => setUserFilter("role", event.target.value)}>
                  <option value="all">Toate</option>
                  <option value="admin">Admin</option>
                  <option value="moderator">Moderator</option>
                  <option value="member">Utilizator</option>
                </select>
              </label>
              <label className="admin-filter-field">
                <span>Status</span>
                <select className="cal-input" value={userFilters.status} onChange={(event) => setUserFilter("status", event.target.value)}>
                  <option value="all">Toate</option>
                  <option value="active">Activ</option>
                  <option value="suspended">Suspendat</option>
                </select>
              </label>
              <label className="admin-filter-field">
                <span>Premium</span>
                <select className="cal-input" value={userFilters.premium} onChange={(event) => setUserFilter("premium", event.target.value)}>
                  <option value="all">Toate</option>
                  <option value="free">Gratuit</option>
                  <option value="trubadur">Trubadur</option>
                  <option value="cronicar">Cronicar</option>
                  <option value="rapsod">Rapsod</option>
                </select>
              </label>
              <fieldset className="admin-filter-group date-range">
                <legend>Data înscrierii</legend>
                <p>Arată conturile create între aceste două date, inclusiv ziua finală.</p>
                <div className="admin-filter-pair">
                  <label><span>De la</span><input className="cal-input compact-date" type="date" value={userFilters.joined_from} onChange={(event) => setUserFilter("joined_from", event.target.value)} /></label>
                  <label><span>Până la</span><input className="cal-input compact-date" type="date" value={userFilters.joined_to} onChange={(event) => setUserFilter("joined_to", event.target.value)} /></label>
                </div>
              </fieldset>
              <fieldset className="admin-filter-group date-range">
                <legend>Ultima autentificare</legend>
                <p>Arată conturile care au intrat în platformă între aceste două date.</p>
                <div className="admin-filter-pair">
                  <label><span>De la</span><input className="cal-input compact-date" type="date" value={userFilters.last_login_from} onChange={(event) => setUserFilter("last_login_from", event.target.value)} /></label>
                  <label><span>Până la</span><input className="cal-input compact-date" type="date" value={userFilters.last_login_to} onChange={(event) => setUserFilter("last_login_to", event.target.value)} /></label>
                </div>
              </fieldset>
              <fieldset className="admin-filter-group post-range">
                <legend>Texte publicate</legend>
                <div className="admin-filter-pair">
                  <label><span>Minim</span><input className="cal-input compact-number" type="number" min="0" value={userFilters.min_posts} onChange={(event) => setUserFilter("min_posts", event.target.value)} /></label>
                  <label><span>Maxim</span><input className="cal-input compact-number" type="number" min="0" value={userFilters.max_posts} onChange={(event) => setUserFilter("max_posts", event.target.value)} /></label>
                </div>
              </fieldset>
            </div>
          ) : null}
          <div className="admin-feed compact">
            {state.users.map((target) => (
              <AdminDataRow
                key={target.id}
                compact
                kicker={`${target.is_admin ? "admin" : target.is_moderator ? "moderator" : "utilizator"} · ${target.is_suspended ? "suspendat" : "activ"}`}
                title={target.username}
                titleHref={profileHref(target.username)}
                meta={<><span>{target.email}</span><span>{formatDateTime(target.created_at)}</span></>}
                preview={`${premiumTierLabel(target.premium_tier)} · ${formatGologani(target.gologani_balance)} · ${formatNumber(target.counts?.posts)} texte · login ${target.last_login_at ? formatDateTime(target.last_login_at) : "niciodată"}`}
              >
                <label className="admin-select-user">
                  <input type="checkbox" checked={selectedUserIds.has(target.id)} onChange={(event) => toggleSelectedUser(target, event.target.checked)} />
                  <span>Selectează</span>
                </label>
                <button className="cal-btn" disabled={Boolean(busy)} onClick={() => changeRoles(target, { is_admin: !target.is_admin, is_moderator: target.is_moderator })}>{target.is_admin ? "Scoate admin" : "Fă admin"}</button>
                <button className="cal-btn" disabled={Boolean(busy)} onClick={() => changeRoles(target, { is_admin: target.is_admin, is_moderator: !target.is_moderator })}>{target.is_moderator ? "Scoate moderator" : "Fă moderator"}</button>
                <button className="cal-btn" disabled={Boolean(busy)} onClick={() => target.is_suspended ? reactivateTarget(target) : suspendTarget(target)}>{target.is_suspended ? "Reactivează" : "Suspendă"}</button>
                <button className="cal-btn" disabled={Boolean(busy)} onClick={() => premiumTarget(target)}>Premium</button>
                <button className="cal-btn" disabled={Boolean(busy)} onClick={() => adjustCoins(target)}>Gologani</button>
                <button className="cal-btn danger" disabled={Boolean(busy)} onClick={() => deleteTarget(target)}>Șterge</button>
              </AdminDataRow>
            ))}
          </div>
        </AdminPanel>
      ) : null}

      {!state.loading && !state.error && canAdmin && activeTab === "email" ? (
        <div className="admin-grid">
          <AdminPanel title="Campanie email" description="Audiență, conținut și coadă de trimitere.">
            <div className="admin-email-compose">
              <div className="admin-controls">
                <label className="admin-mode-option">
                  <input type="radio" name="email-mode" checked={emailMode === "filters"} onChange={() => { setEmailMode("filters"); setEmailPreview(null); }} />
                  <span>Filtre</span>
                </label>
                <label className="admin-mode-option">
                  <input type="radio" name="email-mode" checked={emailMode === "selected"} onChange={() => { setEmailMode("selected"); setEmailPreview(null); }} disabled={!selectedUserIds.size} />
                  <span>Selectați ({formatNumber(selectedUserIds.size)})</span>
                </label>
              </div>
              {emailMode === "filters" ? (
                <div className="admin-controls admin-filter-controls">
                  <input className="cal-input admin-search" value={emailFilters.q} onChange={(event) => setEmailFilter("q", event.target.value)} placeholder="Caută username sau email" />
                  <select className="cal-input" value={emailFilters.role} onChange={(event) => setEmailFilter("role", event.target.value)}>
                    <option value="all">Rol: toate</option>
                    <option value="admin">Admin</option>
                    <option value="moderator">Moderator</option>
                    <option value="member">Utilizator</option>
                  </select>
                  <select className="cal-input" value={emailFilters.status} onChange={(event) => setEmailFilter("status", event.target.value)}>
                    <option value="all">Status: toate</option>
                    <option value="active">Activ</option>
                    <option value="suspended">Suspendat</option>
                  </select>
                  <select className="cal-input" value={emailFilters.premium} onChange={(event) => setEmailFilter("premium", event.target.value)}>
                    <option value="all">Premium: toate</option>
                    <option value="free">Gratuit</option>
                    <option value="trubadur">Trubadur</option>
                    <option value="cronicar">Cronicar</option>
                    <option value="rapsod">Rapsod</option>
                  </select>
                  <input className="cal-input compact-date" type="date" value={emailFilters.joined_from} onChange={(event) => setEmailFilter("joined_from", event.target.value)} aria-label="Înscris de la" />
                  <input className="cal-input compact-date" type="date" value={emailFilters.joined_to} onChange={(event) => setEmailFilter("joined_to", event.target.value)} aria-label="Înscris până la" />
                  <input className="cal-input compact-date" type="date" value={emailFilters.last_login_from} onChange={(event) => setEmailFilter("last_login_from", event.target.value)} aria-label="Ultima autentificare de la" />
                  <input className="cal-input compact-date" type="date" value={emailFilters.last_login_to} onChange={(event) => setEmailFilter("last_login_to", event.target.value)} aria-label="Ultima autentificare până la" />
                  <input className="cal-input compact-number" type="number" min="0" value={emailFilters.min_posts} onChange={(event) => setEmailFilter("min_posts", event.target.value)} placeholder="Min texte" />
                  <input className="cal-input compact-number" type="number" min="0" value={emailFilters.max_posts} onChange={(event) => setEmailFilter("max_posts", event.target.value)} placeholder="Max texte" />
                </div>
              ) : (
                <div className="inline-status">Campania va fi trimisă către utilizatorii selectați din tabul Utilizatori.</div>
              )}
              <input className="cal-input" value={emailSubject} onChange={(event) => setEmailSubject(event.target.value)} placeholder="Subiect email" maxLength="255" />
              <textarea className="cal-input admin-email-html" value={emailHtml} onChange={(event) => setEmailHtml(event.target.value)} spellCheck="false" />
              <div className="button-row">
                <button className="cal-btn" type="button" disabled={Boolean(busy)} onClick={previewEmailAudience}>{busy === "email:preview" ? "Se calculează..." : "Previzualizează destinatarii"}</button>
                <button className="cal-btn primary" type="button" disabled={Boolean(busy)} onClick={sendAdminEmail}>{busy === "email:send" ? "Se trimite..." : "Pune în coadă"}</button>
              </div>
              {emailPreview ? (
                <div className="admin-email-preview">
                  <strong>{formatNumber(emailPreview.recipient_count)} destinatari eligibili</strong>
                  <span>{formatNumber(emailPreview.matched_count)} potriviți înainte de opt-out.</span>
                  {emailPreview.sample?.length ? (
                    <div className="admin-preview-users">
                      {emailPreview.sample.map((sampleUser) => (
                        <a key={sampleUser.id} href={profileHref(sampleUser.username)}>{sampleUser.username}</a>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
          </AdminPanel>
          <AdminPanel
            title="Campanii recente"
            description="Trimiteri, coadă și eșecuri."
            actions={(
              <div className="button-row">
                <button className="cal-btn" type="button" disabled={Boolean(busy)} onClick={sendNotificationTestEmail} title="Trimite către contact@calimara.ro o mostră identică cu notificarea email primită de un utilizator cu emailurile active.">
                  {busy === "email:test-notification" ? "Se trimite testul..." : "Trimite notificare test"}
                </button>
                <button className="cal-btn" type="button" disabled={Boolean(busy)} onClick={processEmailOutbox} title="Trimite acum până la 50 de emailuri din coadă.">
                  {busy === "email:process" ? "Se procesează..." : "Trimite coada acum"}
                </button>
              </div>
            )}
          >
            <div className="admin-feed">
              {state.emailCampaigns.length ? state.emailCampaigns.map((campaign) => (
                <AdminDataRow
                  key={campaign.id}
                  kicker={`email #${campaign.id} · ${campaign.pending_count ? "în coadă" : campaign.failed_count ? "cu erori" : "trimisă"}`}
                  title={campaign.subject}
                  meta={<><span>{formatNumber(campaign.sent_count)} trimise</span><span>{formatDateTime(campaign.created_at)}</span></>}
                  preview={`${formatNumber(campaign.pending_count)} în coadă · ${formatNumber(campaign.failed_count)} eșuate · ${formatNumber(campaign.recipient_count)} destinatari`}
                />
              )) : <StatusPanel title="Nu există campanii email" />}
            </div>
          </AdminPanel>
        </div>
      ) : null}

      {!state.loading && !state.error && canAdmin && activeTab === "content" ? (
        <AdminPanel
          title="Conținut"
          description="Texte, comentarii, audio și forum."
          actions={(
            <div className="admin-controls">
              <select className="cal-input" value={contentType} onChange={(event) => setContentType(event.target.value)}>
                <option value="all">Toate</option>
                <option value="post">Texte</option>
                <option value="comment">Comentarii</option>
                <option value="audio">Audio</option>
                <option value="forum_thread">Discuții</option>
                <option value="forum_reply">Răspunsuri</option>
                <option value="theatre_entry">Teatru</option>
                <option value="stafeta_segment">Ștafeta</option>
              </select>
              <input className="cal-input admin-search" value={contentSearch} onChange={(event) => setContentSearch(event.target.value)} placeholder="Caută conținut" />
            </div>
          )}
        >
          <div className="admin-feed compact">
            {state.content.map((item) => (
              <AdminDataRow
                key={`${item.type}-${item.id}`}
                compact
                kicker={`${contentTypeLabel(item.type)} · ${decisionLabel(item.status)}`}
                title={item.title || contentTypeLabel(item.type)}
                titleHref={contentHref(item)}
                meta={<><span><AdminTextLink href={profileHref(item.author, item.author_url)}>{item.author || "Necunoscut"}</AdminTextLink></span><span>{formatDateTime(item.created_at)}</span></>}
                preview={htmlToText(item.content || "")}
                previewHref={contentHref(item)}
              >
                <button className="cal-btn primary" disabled={Boolean(busy)} onClick={() => moderateListedContent(item, "approve")}>Aprobă</button>
                <button className="cal-btn" disabled={Boolean(busy)} onClick={() => moderateListedContent(item, "reject")}>Respinge</button>
                <button className="cal-btn" disabled={Boolean(busy)} onClick={() => flagListedContent(item)}>Marchează</button>
                {item.type === "post" || item.type === "forum_thread" ? <button className="cal-btn" disabled={Boolean(busy)} onClick={() => editContentTitle(item)}>Titlu</button> : null}
                <button className="cal-btn danger" disabled={Boolean(busy)} onClick={() => deleteListedContent(item)}>Șterge</button>
              </AdminDataRow>
            ))}
          </div>
        </AdminPanel>
      ) : null}

      {!state.loading && !state.error && canAdmin && activeTab === "qaReport" ? (
        <AdminPanel
          title="Raport QA"
          description="Raportul complet al testării este separat de sesizările trimise de utilizatori."
        >
          <AdminStatGrid compact>
            <AdminStat label="Intrări" value={state.qaReportTotal} sub="total" />
            <AdminStat label="Deschise" value={state.qaReportOpenCount} sub="raport" />
            <AdminStat label="Închise" value={state.qaReportClosedCount} sub="raport" />
            <AdminStat label="Afișate" value={state.qaReport.length} sub="în listă" />
          </AdminStatGrid>
          {state.qaReport.length ? (
            <div className="admin-feed">
              {state.qaReport.map((entry) => <AdminQaReportRow key={entry.id} entry={entry} />)}
            </div>
          ) : <StatusPanel title="Nu există raport QA" />}
        </AdminPanel>
      ) : null}

      {!state.loading && !state.error && canAdmin && activeTab === "submissions" ? (
        <AdminPanel
          title="Sesizări"
          description="Feedback, buguri și statusuri."
          actions={(
            <div className="admin-controls">
              <select className="cal-input" value={feedbackKind} onChange={(event) => setFeedbackKind(event.target.value)}>
                <option value="all">Toate</option>
                <option value="feedback">Feedback</option>
                <option value="bug">Buguri</option>
              </select>
              <select className="cal-input" value={feedbackStatus} onChange={(event) => setFeedbackStatus(event.target.value)}>
                <option value="open">Deschise + răspunsuri noi</option>
                <option value="closed">Închise</option>
                <option value="all">Toate statusurile</option>
              </select>
            </div>
          )}
        >
          {state.submissions.length ? (
            <div className="admin-feed">
              {state.submissions.map((item) => {
                const pageUrl = safeExternalUrl(item.page_url);
                const unreadReplies = Math.max(0, Number(item.unread_reply_count) || 0);
                const latestReplyPreview = item.latest_unread_reply_preview || "";
                const preview = unreadReplies && latestReplyPreview
                  ? `${item.message}\n\nRăspuns nou: ${latestReplyPreview}`
                  : item.message;
                return (
                  <AdminDataRow
                    key={item.id}
                    kicker={`${SITE_FEEDBACK_KIND_LABELS[item.kind] || item.kind} · ${SITE_FEEDBACK_STATUS_LABELS[item.status] || item.status}`}
                    badges={unreadReplies ? [{ label: feedbackUnreadReplyLabel(unreadReplies), className: "status-unread" }] : []}
                    className={unreadReplies ? "admin-feedback-has-unread" : ""}
                    title={item.username_snapshot || item.email_snapshot || `Utilizator #${item.user_id || "n/a"}`}
                    titleHref={item.username_snapshot ? profileHref(item.username_snapshot) : ""}
                    meta={<><span>{item.email_snapshot || "fără email"}</span><span>{formatDateTime(item.created_at)}</span>{unreadReplies && item.latest_unread_reply_at ? <span>ultimul răspuns {formatDateTime(item.latest_unread_reply_at)}</span> : null}</>}
                    preview={preview}
                  >
                    {pageUrl ? <a className="cal-btn" href={pageUrl} target="_blank" rel="noreferrer">Pagina</a> : null}
                    <button className="cal-btn primary" type="button" disabled={Boolean(busy)} onClick={() => openFeedbackReply(item)}>Răspunde</button>
                    {item.status === "open" ? (
                      <button className="cal-btn" type="button" disabled={Boolean(busy)} onClick={() => changeFeedbackStatus(item, "closed")}>Închide</button>
                    ) : (
                      <button className="cal-btn" type="button" disabled={Boolean(busy)} onClick={() => changeFeedbackStatus(item, "open")}>Redeschide</button>
                    )}
                    <button className="cal-btn" type="button" disabled={Boolean(busy)} onClick={() => changeFeedbackStatus(item, item.status)}>Notă</button>
                  </AdminDataRow>
                );
              })}
            </div>
          ) : <StatusPanel title="Nu există sesizări" />}
        </AdminPanel>
      ) : null}

      {!state.loading && !state.error && activeTab === "pending" ? (
        <div className="admin-grid">
          <AdminPanel title="În așteptare AI" description="Coada de moderare.">
            {state.pending.length ? (
              <div className="admin-feed">
                {state.pending.map((item) => <AdminWorkRow key={`${item.type}-${item.id}`} item={item} mode="pending" busy={busy} onApprove={approvePending} onReject={rejectPending} />)}
              </div>
            ) : <StatusPanel title="Nu există conținut în așteptare AI" />}
          </AdminPanel>
          <AdminPanel title="Marcate" description="Semnalări automate pentru revizie.">
            {state.flagged.length ? (
              <div className="admin-feed">
                {state.flagged.map((item) => <AdminWorkRow key={item.log_id} item={item} mode="flagged" busy={busy} onApprove={approveFlagged} onReject={rejectFlagged} />)}
              </div>
            ) : <StatusPanel title="Nu există conținut marcat" />}
          </AdminPanel>
        </div>
      ) : null}

      {!state.loading && !state.error && activeTab === "flagged" ? (
        state.flagged.length ? (
          <div className="admin-feed">
            {state.flagged.map((item) => <AdminWorkRow key={item.log_id} item={item} mode="flagged" busy={busy} onApprove={approveFlagged} onReject={rejectFlagged} />)}
          </div>
        ) : <StatusPanel title="Nu există conținut marcat" />
      ) : null}

      {!state.loading && !state.error && activeTab === "reports" ? (
        state.postReports.length ? (
          <div className="admin-feed">
            {state.postReports.map((report) => (
              <AdminReportRow
                key={report.id}
                report={report}
                busy={busy}
                onDismiss={dismissReport}
                onRejectPost={rejectReportedPost}
                onDeletePost={deleteReportedPost}
              />
            ))}
          </div>
        ) : <StatusPanel title="Nu există raportări deschise" />
      ) : null}

      {!state.loading && !state.error && (activeTab === "journal" || activeTab === "audit") ? (
        activeTab === "journal" ? (
          state.logs.length ? <div className="admin-feed">{state.logs.map((log) => <AdminJournalRow key={log.id} log={log} />)}</div> : <StatusPanel title="Jurnalul este gol" />
        ) : (
          <AdminPanel title="Audit administrativ" description="Istoric de acțiuni.">
            <div className="admin-feed">
              {state.audit.map((log) => (
                <AdminDataRow
                  key={log.id}
                  kicker={log.action}
                  title={`${log.target_type} #${log.target_id || "n/a"}`}
                  titleHref={log.target_url}
                  meta={<><span><AdminTextLink href={profileHref(log.actor_username, log.actor_url)}>{log.actor_username}</AdminTextLink></span><span>{formatDateTime(log.created_at)}</span></>}
                  preview={log.reason || ""}
                  previewHref={log.target_url}
                />
              ))}
            </div>
          </AdminPanel>
        )
      ) : null}

      {!state.loading && !state.error && canAdmin && activeTab === "economy" ? (
        <AdminPanel
          title="Magazin și Gologani"
          description="Obiecte, inventare și balanțe."
          actions={(
            <div className="admin-controls">
              <button className="cal-btn" type="button" onClick={() => setActiveTab("artStyles")}>Mostre stil vizual</button>
              <button className="cal-btn primary" type="button" disabled={Boolean(busy)} onClick={createShopItem}>Obiect nou</button>
            </div>
          )}
        >
          <AdminStatGrid compact>
            <AdminStat label="Obiecte active" value={state.overview?.economy?.shop_items_active} sub="magazin" />
            <AdminStat label="Inventar" value={state.overview?.economy?.inventory_items} sub="cumpărări" />
            <AdminStat label="Gologani" value={state.overview?.economy?.gologani_balance_total} sub="în conturi" />
          </AdminStatGrid>
          <div className="admin-feed">
            {state.gologaniRewards.map((reward) => (
              <AdminDataRow
                key={reward.event_type}
                kicker={`recompensă · ${reward.is_active ? "activă" : "inactivă"}`}
                title={reward.label}
                meta={<><span>{reward.event_type}</span><span>{formatGologani(reward.amount)}</span></>}
                preview={reward.description}
              >
                <button className="cal-btn" disabled={Boolean(busy)} onClick={() => updateGologaniRewardAmount(reward)}>Gologani</button>
                <button className="cal-btn" disabled={Boolean(busy)} onClick={() => toggleGologaniReward(reward)}>{reward.is_active ? "Dezactivează" : "Activează"}</button>
              </AdminDataRow>
            ))}
            {state.shop.map((item) => (
              <AdminDataRow key={item.id} kicker={`${slotLabel(item.slot)} · ${item.is_active ? "activ" : "inactiv"}`} title={item.name} meta={<><span>{item.slug}</span><span>{formatGologani(item.price)}</span></>}>
                <button className="cal-btn" disabled={Boolean(busy)} onClick={() => toggleShopItem(item)}>{item.is_active ? "Dezactivează" : "Activează"}</button>
                <button className="cal-btn" disabled={Boolean(busy)} onClick={() => repriceShopItem(item)}>Preț</button>
              </AdminDataRow>
            ))}
          </div>
        </AdminPanel>
      ) : null}

      {!state.loading && !state.error && canAdmin && activeTab === "artStyles" ? (
        <AdminPanel
          title="Stil vizual — Magazin și artefacte"
          description="Patru direcții picturale pentru același obiect (manuscris victorian, PNG cu fundal transparent). Schimbă fundalul de probă pentru a verifica transparența și alege stilul de bază pentru viitorul ghid vizual."
          actions={(
            <div className="admin-controls" role="group" aria-label="Fundal de previzualizare">
              {ART_STYLE_BACKDROPS.map((backdrop) => (
                <button
                  key={backdrop.key}
                  className={`cal-btn${styleBackdrop === backdrop.key ? " primary" : ""}`}
                  type="button"
                  aria-pressed={styleBackdrop === backdrop.key}
                  onClick={() => setStyleBackdrop(backdrop.key)}
                >
                  {backdrop.label}
                </button>
              ))}
            </div>
          )}
        >
          <div className="admin-style-grid">
            {ART_STYLE_MOCKUPS.map((mockup) => (
              <article className="admin-style-card" key={mockup.id}>
                <div className={`admin-style-stage backdrop-${styleBackdrop}`}>
                  <img src={mockup.imageUrl} alt={`${mockup.name} — manuscris victorian`} loading="lazy" />
                </div>
                <div className="admin-style-body">
                  <div className="admin-badges">
                    <span className="piece-card-status">{mockup.code}</span>
                    <span className="piece-card-status">{mockup.medium}</span>
                  </div>
                  <h3 className="admin-style-title">{mockup.name}</h3>
                  <p className="admin-style-desc">{mockup.description}</p>
                </div>
                <div className="admin-style-foot">
                  <div className="admin-style-thumb-group">
                    <div className="cosmetic-preview admin-style-mini" aria-hidden="true">
                      <img src={mockup.imageUrl} alt="" />
                    </div>
                    <span className="admin-style-thumb-label">Miniatură magazin (58px)</span>
                  </div>
                  <a className="cal-btn" href={mockup.imageUrl} target="_blank" rel="noreferrer">Deschide PNG</a>
                </div>
              </article>
            ))}
          </div>
        </AdminPanel>
      ) : null}

      {!state.loading && !state.error && canAdmin && activeTab === "premium" ? (
        <AdminPanel title="Premium" description="Abonamente active pe tier.">
          <AdminStatGrid compact>
            <AdminStat label="Active" value={cards.active_premium_users} sub="abonamente" />
            <AdminStat label="Trubadur" value={premiumByTier.trubadur} sub="tier" />
            <AdminStat label="Cronicar" value={premiumByTier.cronicar} sub="tier" />
            <AdminStat label="Rapsod" value={premiumByTier.rapsod} sub="tier" />
          </AdminStatGrid>
        </AdminPanel>
      ) : null}

      {!state.loading && !state.error && canAdmin && activeTab === "integrations" ? (
        <AdminPanel
          title="Integrări"
          description="Servicii externe: ce chei sunt setate și cum obții fiecare cheie. Valorile secrete nu sunt afișate niciodată."
          actions={<button className="cal-btn" type="button" disabled={integrationsState.loading} onClick={loadIntegrations}>Reîncarcă</button>}
        >
          {integrationsState.error ? <StatusPanel title={integrationsState.error} /> : null}
          {integrationsState.loading && !integrationsState.data ? <StatusPanel title="Se încarcă..." /> : null}
          {integrationsState.data ? (
            <>
              <AdminStatGrid compact>
                <AdminStat label="Complete" value={integrationsState.data.summary.active} sub="configurate și pornite" />
                <AdminStat label="Configurate, oprite" value={integrationsState.data.summary.ready} sub="integrări" />
                <AdminStat label="Incomplete" value={integrationsState.data.summary.incomplete} sub="pornite, dar lipsesc chei" />
                <AdminStat label="Neconfigurate" value={integrationsState.data.summary.not_configured} sub="integrări" />
              </AdminStatGrid>
              <div className="admin-integration-howto">
                <p>Cum adaugi o cheie:</p>
                <ol>
                  <li>Conectează-te la server prin SSH și deschide fișierul: <code>nano {integrationsState.data.env_file}</code></li>
                  <li>Completează valoarea după semnul <code>=</code>, fără ghilimele și fără spații.</li>
                  <li>Salvează (Ctrl+O, Enter, Ctrl+X) și repornește aplicația: <code>{integrationsState.data.restart_command}</code></li>
                  <li>Revino aici și apasă „Reîncarcă”.</li>
                </ol>
              </div>
              <div className="admin-feed">
                {integrationsState.data.integrations.map((item) => <AdminIntegrationRow key={item.key} item={item} />)}
              </div>
            </>
          ) : null}
        </AdminPanel>
      ) : null}
      {!state.loading && !state.error && canAdmin && activeTab === "storage" ? (
        <AdminPanel
          title="Stocare obiecte"
          description="Bucket S3/Hetzner, referințe din baza de date și ștergeri sigure."
          actions={<button className="cal-btn" type="button" disabled={storageState.loading || Boolean(busy)} onClick={refreshStorageObjects}>Reîncarcă</button>}
        >
          <form className="admin-controls admin-filter-controls" onSubmit={applyStorageFilters}>
            <input className="cal-input admin-search" value={storageFilters.prefix} onChange={(event) => setStorageFilter("prefix", event.target.value)} placeholder="Prefix, ex. posts/" />
            <input className="cal-input admin-search" value={storageFilters.q} onChange={(event) => setStorageFilter("q", event.target.value)} placeholder="Caută cheie" />
            <select className="cal-input" value={storageFilters.status} onChange={(event) => setStorageFilter("status", event.target.value)}>
              <option value="all">Toate</option>
              <option value="deletable">Ștergibile</option>
              <option value="referenced">Referențiate</option>
              <option value="unreferenced">Nereferențiate</option>
              <option value="protected">Protejate</option>
            </select>
            <button className="cal-btn primary" type="submit" disabled={storageState.loading || Boolean(busy)}>Aplică</button>
          </form>
          {storageState.error ? <StatusPanel title="Stocarea nu este disponibilă">{storageState.error}</StatusPanel> : null}
          {storageState.summary ? (
            <AdminStatGrid compact>
              <AdminStat label="Afișate" value={storageState.summary.listed_count} sub={`${formatNumber(storageState.summary.raw_count)} citite`} />
              <AdminStat label="Referențiate" value={storageState.summary.referenced_count} sub="DB" />
              <AdminStat label="Ștergibile" value={storageState.summary.deletable_count} sub="safe" />
              <AdminStat label="Pagină" value={storageState.nextCursor ? 1 : 0} sub={storageState.nextCursor ? "mai există" : "final"} />
            </AdminStatGrid>
          ) : null}
          {storageState.loading && !storageState.objects.length ? <StatusPanel title="Se încarcă obiectele" /> : null}
          {storageState.objects.length ? (
            <div className="admin-feed compact">
              {storageState.objects.map((object) => (
                <AdminStorageRow
                  key={object.key}
                  object={object}
                  busy={busy || (storageState.loading ? "storage:loading" : "")}
                  onPreview={previewStorageObject}
                  onDelete={deleteStorageObject}
                  onCleanup={cleanupStorageObject}
                />
              ))}
            </div>
          ) : (!storageState.loading && !storageState.error ? <StatusPanel title="Nu există obiecte pentru filtrele curente" /> : null)}
          {storageState.nextCursor ? (
            <div className="button-row">
              <button className="cal-btn" type="button" disabled={storageState.loading || Boolean(busy)} onClick={loadMoreStorageObjects}>
                {storageState.loading ? "Se încarcă..." : "Încarcă pagina următoare"}
              </button>
            </div>
          ) : null}
        </AdminPanel>
      ) : null}

      {!state.loading && !state.error && canAdmin && activeTab === "performance" ? (
        <AdminPanel
          title="Performanță"
          description="Monitorizare live pentru host, workere, baza de date și cozi."
          actions={(
            <button className="cal-btn" type="button" disabled={performanceState.loading} onClick={() => loadPerformanceData()}>
              {performanceState.loading ? "Se actualizează..." : "Actualizează"}
            </button>
          )}
        >
          {performanceState.error ? <StatusPanel title="Performanța nu s-a putut încărca">{performanceState.error}</StatusPanel> : null}
          {!performanceState.loaded && performanceState.loading ? <StatusPanel title="Se încarcă performanța" /> : null}
          {performanceState.loaded && performanceLive.captured_at ? (
            <div className="admin-performance-stack">
              <AdminStatGrid compact>
                <AdminStat label="CPU" value={formatPercent(performanceHost.cpu_percent)} sub={`${formatNumber(performanceHost.cpu_count || 0)} fire`} />
                <AdminStat label="Load 1m" value={performanceHost.load_average?.one_minute ?? 0} sub="medie" />
                <AdminStat label="RAM" value={formatPercent(performanceHost.memory?.used_percent)} sub={`${formatBytes(performanceHost.memory?.used_bytes)} / ${formatBytes(performanceHost.memory?.total_bytes)}`} />
                <AdminStat label="Swap" value={formatPercent(performanceHost.swap?.used_percent)} sub={formatBytes(performanceHost.swap?.total_bytes)} />
                <AdminStat label="Disk" value={formatPercent(performanceHost.disk?.used_percent)} sub={formatBytes(performanceHost.disk?.free_bytes)} />
                <AdminStat label="Utilizatori activi" value={performanceUsers.active_now || 0} sub={`${formatNumber(performanceUsers.active_window_minutes || 15)} min`} />
                <AdminStat label="Activi 24h" value={performanceUsers.active_24h || 0} sub="utilizatori" />
                <AdminStat label="DB conexiuni" value={`${formatNumber(databaseConnections.active || 0)}/${formatNumber(databaseConnections.max || databaseConnections.total || 0)}`} sub={`${formatNumber(databaseConnections.idle || 0)} idle`} />
                <AdminStat label="DB cache" value={performanceDatabase.available ? formatPercent(performanceDatabase.cache_hit_percent) : "n/a"} sub={performanceDatabase.dialect || "db"} />
                <AdminStat label="DB size" value={performanceDatabase.available ? formatBytes(performanceDatabase.size_bytes) : "n/a"} sub={performanceDatabase.server_version || "test"} />
              </AdminStatGrid>

              <div className="admin-performance-grid">
                <section>
                  <h3>Workere</h3>
                  <AdminPerformanceProcessTable processes={performanceWorkers} />
                </section>
                <section>
                  <h3>Servicii</h3>
                  <AdminKeyValueGrid
                    items={[
                      { label: "Nginx procese", value: formatNumber(performanceProcesses.services?.nginx?.count || 0), sub: formatBytes(performanceProcesses.services?.nginx?.rss_bytes) },
                      { label: "Nginx CPU", value: formatPercent(performanceProcesses.services?.nginx?.cpu_percent || 0) },
                      { label: "Postgres procese", value: formatNumber(performanceProcesses.services?.postgres?.count || 0), sub: formatBytes(performanceProcesses.services?.postgres?.rss_bytes) },
                      { label: "Postgres CPU", value: formatPercent(performanceProcesses.services?.postgres?.cpu_percent || 0) }
                    ]}
                  />
                </section>
                <section>
                  <h3>Cozi</h3>
                  <AdminKeyValueGrid
                    items={[
                      { label: "AI due", value: formatNumber(performanceQueues.ai?.due || 0), sub: `${formatNumber(statusCount(performanceQueues.ai, "pending"))} pending` },
                      { label: "AI processing", value: formatNumber(performanceQueues.ai?.processing || 0) },
                      { label: "AI failed", value: formatNumber(performanceQueues.ai?.failed || 0) },
                      { label: "Email due", value: formatNumber(performanceQueues.email?.due || 0), sub: `${formatNumber(statusCount(performanceQueues.email, "queued"))} queued` },
                      { label: "Email sending", value: formatNumber(performanceQueues.email?.sending || 0) },
                      { label: "Email failed", value: formatNumber(performanceQueues.email?.failed || 0) }
                    ]}
                  />
                </section>
                <section>
                  <h3>Configurare runtime</h3>
                  <AdminKeyValueGrid
                    items={[
                      { label: "Uvicorn workers", value: formatNumber(performanceRuntime.uvicorn_workers || 1) },
                      { label: "DB pool", value: `${formatNumber(performanceRuntime.db_pool_size || 0)} + ${formatNumber(performanceRuntime.db_max_overflow || 0)}` },
                      { label: "Pool timeout", value: `${formatNumber(performanceRuntime.db_pool_timeout || 0)}s` },
                      { label: "Cache public", value: `${formatNumber(performanceRuntime.public_api_cache_ttl_seconds || 0)}s` },
                      { label: "Slow request", value: `${formatNumber(performanceRuntime.slow_request_ms || 0)}ms` },
                      { label: "Python", value: performanceRuntime.python_version || "n/a" }
                    ]}
                  />
                </section>
              </div>

              <section className="admin-performance-history-block">
                <div className="admin-performance-section-head">
                  <h3>Istoric 24h</h3>
                  <span>{performanceState.historyAvailable ? `${formatNumber(performanceState.history.length)} puncte` : "indisponibil"}</span>
                </div>
                <AdminPerformanceHistory points={performanceState.history} />
              </section>

              <p className="admin-performance-updated">Ultima citire: {formatDateTime(performanceState.updatedAt || performanceLive.captured_at)}</p>
            </div>
          ) : null}
        </AdminPanel>
      ) : null}

      {!state.loading && !state.error && canAdmin && activeTab === "jobs" ? (
        <AdminPanel title="Joburi AI" description="Procese asincrone și joburi blocate.">
          <AdminStatGrid compact>
            {Object.entries(jobsByStatus).map(([key, value]) => <AdminStat key={key} label={key} value={value} sub="joburi" />)}
          </AdminStatGrid>
          <div className="admin-feed">
            {state.jobs.map((job) => (
              <AdminDataRow key={job.id} kicker={`${job.job_type} · ${job.status}`} title={`${job.target_type} #${job.target_id}`} titleHref={job.target_url} meta={<><span>{job.attempts}/{job.max_attempts}</span><span>{formatDateTime(job.created_at)}</span></>} preview={job.error_message || ""} previewHref={job.target_url}>
                <button className="cal-btn primary" disabled={Boolean(busy)} onClick={() => retryJob(job)}>Retry</button>
                <button className="cal-btn danger" disabled={Boolean(busy)} onClick={() => cancelJob(job)}>Anulează</button>
              </AdminDataRow>
            ))}
          </div>
        </AdminPanel>
      ) : null}
	      </div>
	      <SiteFeedbackReplyModal
	        state={feedbackReplyState}
	        busy={busy === "site-feedback:reply" ? busy : ""}
	        onReplyChange={(reply) => setFeedbackReplyState((current) => ({ ...current, reply }))}
	        onClose={closeFeedbackReply}
	        onSend={sendFeedbackReply}
	      />
	    </PageShell>
  );
}

export default function AdminRoute({ user }) {
  return <AdminDashboardView user={user} />;
}
