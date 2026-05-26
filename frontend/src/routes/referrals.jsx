import { useState } from "react";
import { FiCheckCircle, FiCopy, FiGift, FiTrendingUp, FiUsers } from "react-icons/fi";
import { fetchMyReferrals } from "../api/referrals.js";
import { formatDateTime, formatGologani, formatNumber } from "../app/format.js";
import { useAsync } from "../app/hooks.js";
import { PageShell, StatusPanel } from "../app/layout.jsx";
import { blogUrl } from "../app/paths.js";

function metricLabel(value, singular, plural) {
  return Number(value) === 1 ? singular : plural;
}

function referralUrl(data) {
  if (!data) return "";
  if (typeof window === "undefined") return data.referral_url || data.referral_path || "";
  return `${window.location.origin}${data.referral_path}`;
}

function rewardText(data) {
  if (!data) return "";
  return `Când un cont creat cu linkul tău câștigă ${formatGologani(data.threshold_gologani)}, primești ${formatNumber(data.reward_days)} zile de ${data.reward_tier || "Trubadur"}.`;
}

function ReferralsMetric({ icon, label, value, sub }) {
  return (
    <div className="referrals-metric">
      <span className="referrals-metric-icon" aria-hidden="true">{icon}</span>
      <span className="referrals-metric-label">{label}</span>
      <strong>{value}</strong>
      {sub ? <small>{sub}</small> : null}
    </div>
  );
}

function ReferralRow({ item, threshold }) {
  const progress = Math.max(0, Math.min(100, Number(item.progress_percent || 0)));
  const rewarded = Boolean(item.rewarded_at);
  const postCount = Number(item.post_count || 0);
  const remaining = Math.max(0, Number(item.remaining_gologani || 0));

  return (
    <article className={`referrals-row ${rewarded ? "rewarded" : ""}`.trim()}>
      <div className="referrals-row-head">
        <div>
          <span className="piece-card-kicker">{rewarded ? "recompensă acordată" : "în progres"}</span>
          <h2>
            <a href={blogUrl(item.username)}>{item.username}</a>
          </h2>
        </div>
        <span className="referrals-row-date">{item.created_at ? formatDateTime(item.created_at) : ""}</span>
      </div>
      <div className="referrals-row-stats" aria-label={`Progres recomandare pentru ${item.username}`}>
        <span>
          <strong>{formatNumber(postCount)}</strong>
          {metricLabel(postCount, "text publicat", "texte publicate")}
        </span>
        <span>
          <strong>{formatGologani(item.gologani_balance)}</strong>
          în cont
        </span>
        <span>
          <strong>{formatGologani(item.earned_gologani)}</strong>
          eligibili
        </span>
      </div>
      <div className="referrals-progress-block">
        <div className="referrals-progress-label">
          <span>{formatGologani(item.earned_gologani)} / {formatGologani(threshold)}</span>
          <strong>{rewarded ? "Recompensă primită" : `${formatGologani(remaining)} rămase`}</strong>
        </div>
        <div className="referrals-progress-track" aria-hidden="true">
          <span style={{ width: `${progress}%` }} />
        </div>
      </div>
    </article>
  );
}

export default function ReferralsView({ user }) {
  const state = useAsync(fetchMyReferrals, [user?.id]);
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState("");

  const copyReferralLink = async (url) => {
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      setCopyError("");
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
      setCopyError("Nu am putut copia linkul automat.");
    }
  };

  if (state.loading) {
    return (
      <PageShell kicker="invitații" title="Invită autori" sub="Încărcăm linkul tău de recomandare.">
        <StatusPanel title="Se încarcă invitațiile" />
      </PageShell>
    );
  }

  if (state.error) {
    return (
      <PageShell kicker="invitații" title="Invită autori" sub="Nu am putut încărca recomandările.">
        <StatusPanel title="Eroare">{state.error}</StatusPanel>
      </PageShell>
    );
  }

  const data = state.data || {};
  const link = referralUrl(data);
  const referrals = data.referrals || [];

  return (
    <PageShell kicker="invitații" title="Invită autori" sub="Linkul tău de recomandare și progresul autorilor invitați.">
      <section className="referrals-page">
        <div className="referrals-link-panel">
          <div className="referrals-link-copy">
            <span className="piece-card-kicker">link recomandare</span>
            <h2>{link}</h2>
            <p>{rewardText(data)}</p>
          </div>
          <div className="referrals-link-actions">
            <input className="cal-input" value={link} readOnly aria-label="Link de recomandare" />
            <button className="cal-btn primary" type="button" onClick={() => copyReferralLink(link)}>
              <FiCopy aria-hidden="true" />
              {copied ? "Copiat" : "Copiază linkul"}
            </button>
          </div>
          {copyError ? <div className="inline-error">{copyError}</div> : null}
        </div>

        <div className="referrals-metric-grid">
          <ReferralsMetric icon={<FiUsers />} label="Autori invitați" value={formatNumber(data.referred_count)} sub={`${formatNumber(data.pending_count)} în progres`} />
          <ReferralsMetric icon={<FiGift />} label="Recompense" value={formatNumber(data.rewarded_count)} sub={`${formatNumber(data.reward_days)} zile fiecare`} />
          <ReferralsMetric icon={<FiTrendingUp />} label="Prag recompensă" value={formatGologani(data.threshold_gologani)} sub={data.reward_tier || "Trubadur"} />
          <ReferralsMetric icon={<FiCheckCircle />} label="Status" value={referrals.length ? "activ" : "fără invitați"} sub="recomandări personale" />
        </div>

        <section className="referrals-list-panel" aria-labelledby="referrals-list-title">
          <div className="referrals-list-head">
            <div>
              <span className="piece-card-kicker">autori invitați</span>
              <h2 id="referrals-list-title">Toți utilizatorii invitați de tine</h2>
            </div>
            <span>{formatNumber(referrals.length)} total</span>
          </div>
          {referrals.length ? (
            <div className="referrals-list">
              {referrals.map((item) => <ReferralRow key={item.user_id} item={item} threshold={data.threshold_gologani} />)}
            </div>
          ) : (
            <StatusPanel title="Nu ai încă autori invitați">Distribuie linkul de mai sus ca să înceapă progresul.</StatusPanel>
          )}
        </section>
      </section>
    </PageShell>
  );
}
