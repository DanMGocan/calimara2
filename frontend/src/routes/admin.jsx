import { useCallback, useEffect, useState } from "react";
import { cancelAdminJob, createAdminEmailCampaign, deleteAdminContent, deleteAdminUser, fetchAdminAuditLog, fetchAdminContent, fetchAdminEmailCampaigns, fetchAdminJobs, fetchAdminOverview, fetchAdminSiteFeedback, fetchAdminUsers, moderateAdminContent, previewAdminEmail, reactivateAdminUser, retryAdminJob, rollupAdminMetrics, suspendAdminUser, updateAdminContent, updateAdminSiteFeedback, updateAdminUserPremium, updateAdminUserRoles, adjustAdminUserGologani } from "../api/admin.js";
import { createAdminShopItem, fetchAdminShopItems, updateAdminShopItem } from "../api/economy.js";
import { fetchExtendedModerationStats, fetchModerationLogs, fetchModerationQueue, fetchModerationStats, fetchPendingModerationContent, fetchPostReports, moderateContent, reviewModerationLog, reviewPostReport } from "../api/moderation.js";
import { contentTypeLabel, decisionLabel, formatDateTime, formatGologani, formatNumber, formatScore, htmlToText, slotLabel } from "../app/format.js";
import { AuthRequired, PageShell, StatusPanel } from "../app/layout.jsx";

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

function premiumTierLabel(tier) {
  return PREMIUM_TIER_LABELS[tier] || tier || PREMIUM_TIER_LABELS.free;
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

function AdminStat({ label, value, sub }) {
  return (
    <div className="admin-stat">
      <span className="rail-label">{label}</span>
      <span className="rail-count">{Number(value ?? 0).toLocaleString("ro-RO")}</span>
      {sub ? <span className="rail-sub">{sub}</span> : null}
    </div>
  );
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
          <h2 className="admin-row-title">{title}</h2>
        </div>
        <div className="admin-row-meta">
          <span>{author}</span>
          {createdAt ? <span>{formatDateTime(createdAt)}</span> : null}
        </div>
      </div>
      {preview ? <p className="admin-preview">{htmlToText(preview)}</p> : null}
      {reason ? <p className="admin-reason">{reason}</p> : null}
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
          <h2 className="admin-row-title">{log.content_title || contentTypeLabel(log.content_type)}</h2>
        </div>
        <div className="admin-row-meta">
          {log.content_author ? <span>{log.content_author}</span> : null}
          {log.created_at ? <span>{formatDateTime(log.created_at)}</span> : null}
        </div>
      </div>
      {log.content_preview ? <p className="admin-preview">{htmlToText(log.content_preview)}</p> : null}
      <div className="admin-journal-grid">
        <span>toxicitate {formatScore(log.toxicity_score)}</span>
        {log.moderator ? <span>moderator {log.moderator}</span> : null}
        {log.moderated_at ? <span>moderat {formatDateTime(log.moderated_at)}</span> : null}
      </div>
      {log.ai_reason ? <p className="admin-reason">{log.ai_reason}</p> : null}
      {log.human_reason ? <p className="admin-reason">{log.human_reason}</p> : null}
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
  const title = report.post_title || "Postare ștearsă";
  return (
    <article className="admin-row">
      <div className="admin-row-head">
        <div>
          <div className="admin-badges">
            <span className="piece-card-status">{reportTypeLabel(report.reason_type)}</span>
            <span className="piece-card-status">{decisionLabel(report.status)}</span>
          </div>
          <h2 className="admin-row-title">{title}</h2>
        </div>
        <div className="admin-row-meta">
          {report.post_author ? <span>{report.post_author}</span> : null}
          {report.created_at ? <span>{formatDateTime(report.created_at)}</span> : null}
        </div>
      </div>
      {details ? <p className="admin-preview">{details}</p> : null}
      {evidence ? <p className="admin-reason">{evidence}</p> : null}
      <div className="admin-journal-grid">
        {report.reporter_username ? <span>raportat de {report.reporter_username}</span> : null}
        {report.reviewer_username ? <span>revizuit de {report.reviewer_username}</span> : null}
        {report.reviewed_at ? <span>{formatDateTime(report.reviewed_at)}</span> : null}
      </div>
      {report.review_note ? <p className="admin-reason">{report.review_note}</p> : null}
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
function AdminPanel({ title, children, actions }) {
  return (
    <section className="admin-panel">
      <div className="admin-panel-head">
        <h2>{title}</h2>
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
function AdminDataRow({ kicker, title, meta, preview, children }) {
  return (
    <article className="admin-row">
      <div className="admin-row-head">
        <div>
          <div className="admin-badges">
            {kicker ? <span className="piece-card-status">{kicker}</span> : null}
          </div>
          <h2 className="admin-row-title">{title}</h2>
        </div>
        {meta ? <div className="admin-row-meta">{meta}</div> : null}
      </div>
      {preview ? <p className="admin-preview">{preview}</p> : null}
      {children ? <div className="admin-actions">{children}</div> : null}
    </article>
  );
}
function AdminDashboardView({ user }) {
  const canAdmin = Boolean(user?.is_admin);
  const canModerate = Boolean(user?.is_admin || user?.is_moderator);
  const [activeTab, setActiveTab] = useState(canAdmin ? "overview" : "pending");
  const [userSearch, setUserSearch] = useState("");
  const [userFilters, setUserFilters] = useState(DEFAULT_USER_FILTERS);
  const [contentSearch, setContentSearch] = useState("");
  const [contentType, setContentType] = useState("all");
  const [feedbackKind, setFeedbackKind] = useState("all");
  const [feedbackStatus, setFeedbackStatus] = useState("open");
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
    jobs: [],
    audit: [],
    shop: [],
    submissions: [],
    submissionsTotal: 0,
    emailCampaigns: [],
    error: "",
    loading: true
  });
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");

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
        jobs: [],
        audit: [],
        shop: [],
        submissions: [],
        submissionsTotal: 0
      };
      if (canAdmin) {
        const [overview, users, content, jobs, audit, shop, submissions, emailCampaigns] = await Promise.all([
          fetchAdminOverview(),
          fetchAdminUsers({ q: userSearch, ...cleanFilters(userFilters), limit: 50 }),
          fetchAdminContent({ q: contentSearch, content_type: contentType, limit: 50 }),
          fetchAdminJobs({ limit: 50 }),
          fetchAdminAuditLog({ limit: 100 }),
          fetchAdminShopItems(),
          fetchAdminSiteFeedback({ kind: feedbackKind, status: feedbackStatus, limit: 50 }),
          fetchAdminEmailCampaigns({ limit: 20 })
        ]);
        adminData = {
          overview,
          users: users.users || [],
          content: content.content || [],
          jobs: jobs.jobs || [],
          audit: audit.logs || [],
          shop: Array.isArray(shop) ? shop : [],
          submissions: submissions.submissions || [],
          submissionsTotal: submissions.total || 0,
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

  const runRollup = () => {
    const date = adminPrompt("Dată rollup YYYY-MM-DD, gol pentru ieri", "");
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

  const tabs = canAdmin
    ? [
        ["overview", "Ansamblu", state.overview?.cards?.pending_moderation],
        ["users", "Utilizatori", state.users.length],
        ["content", "Conținut", state.content.length],
        ["submissions", "Sesizări", state.submissionsTotal],
        ["email", "Email", state.emailCampaigns.length],
        ["pending", "Moderare", state.pending.length + state.flagged.length],
        ["reports", "Raportări", state.postReports.length],
        ["journal", "Jurnal", state.logs.length],
        ["economy", "Economie", state.shop.length],
        ["premium", "Premium", state.overview?.cards?.active_premium_users],
        ["jobs", "Joburi", state.jobs.length],
        ["audit", "Audit", state.audit.length]
      ]
    : [
        ["pending", "În așteptare AI", state.pending.length],
        ["flagged", "Marcate", state.flagged.length],
        ["reports", "Raportări", state.postReports.length],
        ["journal", "Jurnal", state.logs.length]
      ];

  const cards = state.overview?.cards || {};
  const premiumByTier = state.overview?.premium?.by_tier || {};
  const jobsByStatus = state.overview?.jobs?.by_status || {};
  const traffic = state.overview?.traffic || {};

  return (
    <PageShell kicker="admin" title={canAdmin ? "Admin" : "Moderare"} sub={`Conectat ca ${user.username}.`}>
      <div className="admin-stat-grid">
        <AdminStat label="Utilizatori" value={canAdmin ? cards.total_users : state.stats?.pending_count} sub={canAdmin ? `${formatNumber(cards.new_users)} noi` : "în coadă"} />
        <AdminStat label="Conținut" value={canAdmin ? cards.total_posts : state.stats?.flagged_count} sub={canAdmin ? `${formatNumber(cards.pending_moderation)} pending` : "marcate"} />
        <AdminStat label="Vizualizări" value={canAdmin ? traffic.unique_views : state.stats?.today_actions} sub={canAdmin ? "reale" : "decizii azi"} />
        <AdminStat label="Premium" value={canAdmin ? cards.active_premium_users : state.extendedStats?.total_logs} sub={canAdmin ? "active" : "jurnal"} />
        <AdminStat label="Joburi" value={canAdmin ? cards.failed_jobs : state.extendedStats?.pending_review_count} sub={canAdmin ? "eșuate" : "revizie"} />
      </div>

      <div className="admin-tabs" role="tablist" aria-label="Admin">
        {tabs.map(([key, label, count]) => (
          <button key={key} className={`admin-tab ${activeTab === key ? "active" : ""}`} type="button" role="tab" aria-selected={activeTab === key} onClick={() => setActiveTab(key)}>
            <span>{label}</span>
            <strong>{formatNumber(count || 0)}</strong>
          </button>
        ))}
      </div>

      {state.loading ? <StatusPanel title="Se încarcă" /> : null}
      {state.error ? <StatusPanel title="Nu am putut încărca adminul">{state.error}</StatusPanel> : null}
      {status ? <div className="inline-error">{status}</div> : null}

      {!state.loading && !state.error && canAdmin && activeTab === "overview" ? (
        <div className="admin-grid">
          <AdminPanel title="Operațiuni" actions={<button className="cal-btn" type="button" disabled={Boolean(busy)} onClick={runRollup}>Rulează rollup</button>}>
            <div className="admin-mini-grid">
              <AdminStat label="Comentarii" value={cards.total_comments} sub={`${formatNumber(cards.new_comments)} noi`} />
              <AdminStat label="Suspendați" value={cards.suspended_users} sub="conturi" />
              <AdminStat label="Marcate" value={cards.flagged_moderation} sub="moderare" />
              <AdminStat label="Magazin" value={cards.shop_items} sub="obiecte" />
            </div>
          </AdminPanel>
          <AdminPanel title="Trafic">
            <div className="admin-mini-grid">
              <AdminStat label="Total" value={traffic.total_views} sub="views" />
              <AdminStat label="Reale" value={traffic.unique_views} sub="dedup" />
              <AdminStat label="Boți" value={traffic.bot_views} sub={`${traffic.bot_percentage || 0}%`} />
            </div>
          </AdminPanel>
        </div>
      ) : null}

      {!state.loading && !state.error && canAdmin && activeTab === "users" ? (
        <AdminPanel
          title="Utilizatori"
          actions={(
            <div className="admin-controls admin-filter-controls">
              <input className="cal-input admin-search" value={userSearch} onChange={(event) => setUserSearch(event.target.value)} placeholder="Caută username sau email" />
              <select className="cal-input" value={userFilters.role} onChange={(event) => setUserFilter("role", event.target.value)}>
                <option value="all">Rol: toate</option>
                <option value="admin">Admin</option>
                <option value="moderator">Moderator</option>
                <option value="member">Utilizator</option>
              </select>
              <select className="cal-input" value={userFilters.status} onChange={(event) => setUserFilter("status", event.target.value)}>
                <option value="all">Status: toate</option>
                <option value="active">Activ</option>
                <option value="suspended">Suspendat</option>
              </select>
              <select className="cal-input" value={userFilters.premium} onChange={(event) => setUserFilter("premium", event.target.value)}>
                <option value="all">Premium: toate</option>
                <option value="free">Gratuit</option>
                <option value="trubadur">Trubadur</option>
                <option value="cronicar">Cronicar</option>
                <option value="rapsod">Rapsod</option>
              </select>
              <input className="cal-input compact-date" type="date" value={userFilters.joined_from} onChange={(event) => setUserFilter("joined_from", event.target.value)} aria-label="Înscris de la" />
              <input className="cal-input compact-date" type="date" value={userFilters.joined_to} onChange={(event) => setUserFilter("joined_to", event.target.value)} aria-label="Înscris până la" />
              <input className="cal-input compact-date" type="date" value={userFilters.last_login_from} onChange={(event) => setUserFilter("last_login_from", event.target.value)} aria-label="Ultima autentificare de la" />
              <input className="cal-input compact-date" type="date" value={userFilters.last_login_to} onChange={(event) => setUserFilter("last_login_to", event.target.value)} aria-label="Ultima autentificare până la" />
              <input className="cal-input compact-number" type="number" min="0" value={userFilters.min_posts} onChange={(event) => setUserFilter("min_posts", event.target.value)} placeholder="Min texte" />
              <input className="cal-input compact-number" type="number" min="0" value={userFilters.max_posts} onChange={(event) => setUserFilter("max_posts", event.target.value)} placeholder="Max texte" />
              <button className="cal-btn" type="button" disabled={!selectedUserIds.size} onClick={emailSelectedUsers}>Email selectați</button>
            </div>
          )}
        >
          <div className="admin-feed">
            {state.users.map((target) => (
              <AdminDataRow
                key={target.id}
                kicker={`${target.is_admin ? "admin" : target.is_moderator ? "moderator" : "utilizator"} · ${target.is_suspended ? "suspendat" : "activ"}`}
                title={target.username}
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
          <AdminPanel title="Campanie email">
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
                      {emailPreview.sample.map((sampleUser) => <span key={sampleUser.id}>{sampleUser.username}</span>)}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
          </AdminPanel>
          <AdminPanel title="Campanii recente">
            <div className="admin-feed">
              {state.emailCampaigns.length ? state.emailCampaigns.map((campaign) => (
                <AdminDataRow
                  key={campaign.id}
                  kicker={`email #${campaign.id}`}
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
          actions={(
            <div className="admin-controls">
              <select className="cal-input" value={contentType} onChange={(event) => setContentType(event.target.value)}>
                <option value="all">Toate</option>
                <option value="post">Texte</option>
                <option value="comment">Comentarii</option>
                <option value="audio">Audio</option>
                <option value="forum_thread">Discuții</option>
                <option value="forum_reply">Răspunsuri</option>
              </select>
              <input className="cal-input admin-search" value={contentSearch} onChange={(event) => setContentSearch(event.target.value)} placeholder="Caută conținut" />
            </div>
          )}
        >
          <div className="admin-feed">
            {state.content.map((item) => (
              <AdminDataRow
                key={`${item.type}-${item.id}`}
                kicker={`${contentTypeLabel(item.type)} · ${decisionLabel(item.status)}`}
                title={item.title || contentTypeLabel(item.type)}
                meta={<><span>{item.author || "Necunoscut"}</span><span>{formatDateTime(item.created_at)}</span></>}
                preview={htmlToText(item.content || "")}
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

      {!state.loading && !state.error && canAdmin && activeTab === "submissions" ? (
        <AdminPanel
          title="Sesizări"
          actions={(
            <div className="admin-controls">
              <select className="cal-input" value={feedbackKind} onChange={(event) => setFeedbackKind(event.target.value)}>
                <option value="all">Toate</option>
                <option value="feedback">Feedback</option>
                <option value="bug">Buguri</option>
              </select>
              <select className="cal-input" value={feedbackStatus} onChange={(event) => setFeedbackStatus(event.target.value)}>
                <option value="open">Deschise</option>
                <option value="closed">Închise</option>
                <option value="all">Toate statusurile</option>
              </select>
            </div>
          )}
        >
          {state.submissions.length ? (
            <div className="admin-feed">
              {state.submissions.map((item) => (
                <AdminDataRow
                  key={item.id}
                  kicker={`${SITE_FEEDBACK_KIND_LABELS[item.kind] || item.kind} · ${SITE_FEEDBACK_STATUS_LABELS[item.status] || item.status}`}
                  title={item.username_snapshot || item.email_snapshot || `Utilizator #${item.user_id || "n/a"}`}
                  meta={<><span>{item.email_snapshot || "fără email"}</span><span>{formatDateTime(item.created_at)}</span></>}
                  preview={item.message}
                >
                  {item.page_url ? <a className="cal-btn" href={item.page_url} target="_blank" rel="noreferrer">Pagina</a> : null}
                  {item.status === "open" ? (
                    <button className="cal-btn primary" type="button" disabled={Boolean(busy)} onClick={() => changeFeedbackStatus(item, "closed")}>Închide</button>
                  ) : (
                    <button className="cal-btn" type="button" disabled={Boolean(busy)} onClick={() => changeFeedbackStatus(item, "open")}>Redeschide</button>
                  )}
                  <button className="cal-btn" type="button" disabled={Boolean(busy)} onClick={() => changeFeedbackStatus(item, item.status)}>Notă</button>
                </AdminDataRow>
              ))}
            </div>
          ) : <StatusPanel title="Nu există sesizări" />}
        </AdminPanel>
      ) : null}

      {!state.loading && !state.error && activeTab === "pending" ? (
        <div className="admin-grid">
          <AdminPanel title="În așteptare AI">
            {state.pending.length ? (
              <div className="admin-feed">
                {state.pending.map((item) => <AdminWorkRow key={`${item.type}-${item.id}`} item={item} mode="pending" busy={busy} onApprove={approvePending} onReject={rejectPending} />)}
              </div>
            ) : <StatusPanel title="Nu există conținut în așteptare AI" />}
          </AdminPanel>
          <AdminPanel title="Marcate">
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
          <AdminPanel title="Audit administrativ">
            <div className="admin-feed">
              {state.audit.map((log) => (
                <AdminDataRow key={log.id} kicker={log.action} title={`${log.target_type} #${log.target_id || "n/a"}`} meta={<><span>{log.actor_username}</span><span>{formatDateTime(log.created_at)}</span></>} preview={log.reason || ""} />
              ))}
            </div>
          </AdminPanel>
        )
      ) : null}

      {!state.loading && !state.error && canAdmin && activeTab === "economy" ? (
        <AdminPanel title="Magazin și Gologani" actions={<button className="cal-btn primary" type="button" disabled={Boolean(busy)} onClick={createShopItem}>Obiect nou</button>}>
          <div className="admin-mini-grid">
            <AdminStat label="Obiecte active" value={state.overview?.economy?.shop_items_active} sub="magazin" />
            <AdminStat label="Inventar" value={state.overview?.economy?.inventory_items} sub="cumpărări" />
            <AdminStat label="Gologani" value={state.overview?.economy?.gologani_balance_total} sub="în conturi" />
          </div>
          <div className="admin-feed">
            {state.shop.map((item) => (
              <AdminDataRow key={item.id} kicker={`${slotLabel(item.slot)} · ${item.is_active ? "activ" : "inactiv"}`} title={item.name} meta={<><span>{item.slug}</span><span>{formatGologani(item.price)}</span></>}>
                <button className="cal-btn" disabled={Boolean(busy)} onClick={() => toggleShopItem(item)}>{item.is_active ? "Dezactivează" : "Activează"}</button>
                <button className="cal-btn" disabled={Boolean(busy)} onClick={() => repriceShopItem(item)}>Preț</button>
              </AdminDataRow>
            ))}
          </div>
        </AdminPanel>
      ) : null}

      {!state.loading && !state.error && canAdmin && activeTab === "premium" ? (
        <AdminPanel title="Premium">
          <div className="admin-mini-grid">
            <AdminStat label="Active" value={cards.active_premium_users} sub="abonamente" />
            <AdminStat label="Trubadur" value={premiumByTier.trubadur} sub="tier" />
            <AdminStat label="Cronicar" value={premiumByTier.cronicar} sub="tier" />
            <AdminStat label="Rapsod" value={premiumByTier.rapsod} sub="tier" />
          </div>
        </AdminPanel>
      ) : null}

      {!state.loading && !state.error && canAdmin && activeTab === "jobs" ? (
        <AdminPanel title="Joburi AI">
          <div className="admin-mini-grid">
            {Object.entries(jobsByStatus).map(([key, value]) => <AdminStat key={key} label={key} value={value} sub="joburi" />)}
          </div>
          <div className="admin-feed">
            {state.jobs.map((job) => (
              <AdminDataRow key={job.id} kicker={`${job.job_type} · ${job.status}`} title={`${job.target_type} #${job.target_id}`} meta={<><span>{job.attempts}/{job.max_attempts}</span><span>{formatDateTime(job.created_at)}</span></>} preview={job.error_message || ""}>
                <button className="cal-btn primary" disabled={Boolean(busy)} onClick={() => retryJob(job)}>Retry</button>
                <button className="cal-btn danger" disabled={Boolean(busy)} onClick={() => cancelJob(job)}>Anulează</button>
              </AdminDataRow>
            ))}
          </div>
        </AdminPanel>
      ) : null}
    </PageShell>
  );
}

export default function AdminRoute({ user }) {
  return <AdminDashboardView user={user} />;
}
