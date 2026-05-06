import { useCallback, useEffect, useState } from "react";
import { cancelAdminJob, deleteAdminContent, deleteAdminUser, fetchAdminAuditLog, fetchAdminContent, fetchAdminJobs, fetchAdminOverview, fetchAdminUsers, moderateAdminContent, reactivateAdminUser, retryAdminJob, rollupAdminMetrics, suspendAdminUser, updateAdminContent, updateAdminUserPremium, updateAdminUserRoles, adjustAdminUserGologani } from "../api/admin.js";
import { createAdminShopItem, fetchAdminShopItems, updateAdminShopItem } from "../api/economy.js";
import { fetchExtendedModerationStats, fetchModerationLogs, fetchModerationQueue, fetchModerationStats, fetchPendingModerationContent, moderateContent, reviewModerationLog } from "../api/moderation.js";
import { contentTypeLabel, decisionLabel, formatDateTime, formatGologani, formatNumber, formatScore, htmlToText, slotLabel } from "../app/format.js";
import { AuthRequired, PageShell, StatusPanel } from "../app/layout.jsx";

const PREMIUM_TIER_LABELS = {
  free: "Gratuit",
  trubadur: "Trubadur",
  cronicar: "Cronicar",
  rapsod: "Rapsod"
};

function premiumTierLabel(tier) {
  return PREMIUM_TIER_LABELS[tier] || tier || PREMIUM_TIER_LABELS.free;
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
  const [contentSearch, setContentSearch] = useState("");
  const [contentType, setContentType] = useState("all");
  const [state, setState] = useState({
    overview: null,
    stats: null,
    extendedStats: null,
    pending: [],
    flagged: [],
    logs: [],
    users: [],
    content: [],
    jobs: [],
    audit: [],
    shop: [],
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
      const [stats, extendedStats, pending, flagged, logs] = await Promise.all([
        fetchModerationStats(),
        fetchExtendedModerationStats(),
        fetchPendingModerationContent(),
        fetchModerationQueue(),
        fetchModerationLogs({ limit: 100 })
      ]);
      let adminData = {
        overview: null,
        users: [],
        content: [],
        jobs: [],
        audit: [],
        shop: []
      };
      if (canAdmin) {
        const [overview, users, content, jobs, audit, shop] = await Promise.all([
          fetchAdminOverview(),
          fetchAdminUsers({ q: userSearch, limit: 50 }),
          fetchAdminContent({ q: contentSearch, content_type: contentType, limit: 50 }),
          fetchAdminJobs({ limit: 50 }),
          fetchAdminAuditLog({ limit: 100 }),
          fetchAdminShopItems()
        ]);
        adminData = {
          overview,
          users: users.users || [],
          content: content.content || [],
          jobs: jobs.jobs || [],
          audit: audit.logs || [],
          shop: Array.isArray(shop) ? shop : []
        };
      }
      setState({
        stats,
        extendedStats,
        pending: pending.content || [],
        flagged: flagged.queue || [],
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
  }, [canAdmin, canModerate, contentSearch, contentType, userSearch]);

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

  const tabs = canAdmin
    ? [
        ["overview", "Ansamblu", state.overview?.cards?.pending_moderation],
        ["users", "Utilizatori", state.users.length],
        ["content", "Conținut", state.content.length],
        ["pending", "Moderare", state.pending.length + state.flagged.length],
        ["journal", "Jurnal", state.logs.length],
        ["economy", "Economie", state.shop.length],
        ["premium", "Premium", state.overview?.cards?.active_premium_users],
        ["jobs", "Joburi", state.jobs.length],
        ["audit", "Audit", state.audit.length]
      ]
    : [
        ["pending", "În așteptare AI", state.pending.length],
        ["flagged", "Marcate", state.flagged.length],
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
          actions={<input className="cal-input admin-search" value={userSearch} onChange={(event) => setUserSearch(event.target.value)} placeholder="Caută username sau email" />}
        >
          <div className="admin-feed">
            {state.users.map((target) => (
              <AdminDataRow
                key={target.id}
                kicker={`${target.is_admin ? "admin" : target.is_moderator ? "moderator" : "utilizator"} · ${target.is_suspended ? "suspendat" : "activ"}`}
                title={target.username}
                meta={<><span>{target.email}</span><span>{formatDateTime(target.created_at)}</span></>}
                preview={`${premiumTierLabel(target.premium_tier)} · ${formatGologani(target.gologani_balance)} · ${formatNumber(target.counts?.posts)} texte`}
              >
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
