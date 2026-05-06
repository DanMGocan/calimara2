import { useEffect, useMemo, useState } from "react";
import { FiCheckCircle, FiCreditCard, FiHeadphones, FiStar, FiTrendingUp } from "react-icons/fi";
import { AUTH_GOOGLE_PATH } from "../api/auth.js";
import { fetchAudioConversionQuota } from "../api/audio.js";
import { fetchPremiumPlans, openPremiumPortal, startPremiumCheckout } from "../api/premium.js";
import { PROFILE_TIER_BADGES } from "../app/constants.js";
import { formatDateTime, formatNumber } from "../app/format.js";
import { useAsync } from "../app/hooks.js";
import { PageShell } from "../app/layout.jsx";

const TIER_RANK = {
  free: 0,
  trubadur: 1,
  cronicar: 2,
  rapsod: 3
};

function tierByKey(key, tiers) {
  return tiers.find((tier) => tier.key === key) || tiers[0] || null;
}

function tierName(key, tiers) {
  return tierByKey(key, tiers)?.name || PROFILE_TIER_BADGES[key]?.label || "Premium";
}

function planAccessLabel(user, tiers) {
  if (!user?.is_premium) return "Cont gratuit";
  return tierName(user.premium_tier, tiers);
}

function DashboardMetric({ icon, label, value, sub }) {
  return (
    <div className="premium-metric">
      <span className="premium-metric-icon" aria-hidden="true">{icon}</span>
      <span className="premium-metric-label">{label}</span>
      <strong>{value}</strong>
      {sub ? <small>{sub}</small> : null}
    </div>
  );
}

function TierCard({ tier, user, selected, busy, onSelect, onStart }) {
  const active = Boolean(user?.is_premium && user.premium_tier === tier.key);
  const included = Boolean(user?.is_premium && TIER_RANK[user.premium_tier] >= TIER_RANK[tier.key]);
  const unavailable = !tier.available && !user?.is_premium;
  const disabled = busy || Boolean(user?.is_premium) || unavailable;
  const tierBadge = PROFILE_TIER_BADGES[tier.key] || PROFILE_TIER_BADGES.trubadur;
  const buttonLabel = unavailable
    ? "Indisponibil"
    : user?.is_premium
      ? active ? "Plan activ" : included ? "Inclus în planul tău" : "Schimbă din portal"
      : selected ? "Continuă cu acest plan" : "Alege planul";

  return (
    <article className={`premium-tier-card ${tierBadge.className} ${selected ? "selected" : ""} ${active ? "active" : ""}`}>
      <div className="premium-tier-head">
        <div>
          <div className="piece-card-kicker">{tier.eyebrow}</div>
          <h2>{tier.name}</h2>
        </div>
        {active ? <span className="premium-tier-badge">activ</span> : included ? <span className="premium-tier-badge muted">inclus</span> : null}
      </div>
      <div className="premium-price">
        <strong>{tier.price}</strong>
        <span>{tier.cadence}</span>
      </div>
      <p>{tier.summary}</p>
      <ul className="premium-benefit-list">
        {tier.benefits.map((benefit) => (
          <li key={benefit}>
            <FiCheckCircle aria-hidden="true" />
            <span>{benefit}</span>
          </li>
        ))}
      </ul>
      <button
        className={`cal-btn ${selected && !user?.is_premium ? "primary" : ""}`}
        type="button"
        disabled={disabled}
        onClick={() => {
          if (!user?.is_premium && !selected) {
            onSelect(tier.key);
            return;
          }
          onStart(tier.key);
        }}
      >
        {buttonLabel}
      </button>
    </article>
  );
}

function PremiumView({ user }) {
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [selectedTier, setSelectedTier] = useState(user?.premium_tier && user.premium_tier !== "free" ? user.premium_tier : "trubadur");
  const plansState = useAsync(fetchPremiumPlans, []);
  const tiers = plansState.data || [];
  const selectedTierDetails = useMemo(() => tierByKey(selectedTier, tiers), [selectedTier, tiers]);
  const selectedTierAvailable = Boolean(selectedTierDetails?.available);
  const selectedTierName = selectedTierDetails?.name || tierName(selectedTier, tiers);
  const activeTier = user?.is_premium ? tierByKey(user.premium_tier, tiers) : null;
  const quotaState = useAsync(
    () => (user?.has_audio_access ? fetchAudioConversionQuota() : Promise.resolve(null)),
    [user?.id, user?.has_audio_access, user?.premium_until]
  );

  useEffect(() => {
    if (tiers.length && !tiers.some((tier) => tier.key === selectedTier)) {
      setSelectedTier(tiers[0].key);
    }
  }, [tiers, selectedTier]);

  useEffect(() => {
    if (user?.is_premium && user.premium_tier && user.premium_tier !== "free") {
      setSelectedTier(user.premium_tier);
    }
  }, [user?.id, user?.is_premium, user?.premium_tier]);

  const openStripe = async (tier = selectedTier) => {
    if (!user) {
      window.location.href = AUTH_GOOGLE_PATH;
      return;
    }
    setBusy(true);
    setStatus("");
    try {
      const requestedTier = tierByKey(tier, tiers);
      if (!user.is_premium && requestedTier && !requestedTier.available) {
        setStatus("Planul selectat nu este disponibil pentru plată.");
        setBusy(false);
        return;
      }
      const response = user.is_premium ? await openPremiumPortal() : await startPremiumCheckout(tier);
      window.location.href = response.url;
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut deschide pagina de plată.");
      setBusy(false);
    }
  };

  return (
    <PageShell
      kicker="premium"
      title="Dashboard Premium"
      sub="Alege, compară și gestionează planurile pentru super-aprecieri, diacritice și audio."
    >
      <section className="premium-dashboard">
        <div className="premium-dashboard-head">
          <div>
            <div className="piece-card-kicker">abonament</div>
            <h2>{user?.is_premium ? "Planul tău este activ" : "Alege un plan pentru contul tău"}</h2>
            <p>
              {user?.is_premium
                ? `Folosești ${activeTier?.name ?? "Premium"}${user.premium_until ? ` până la ${formatDateTime(user.premium_until)}` : ""}.`
                : `Plan selectat: ${selectedTierName}. Checkout-ul este procesat securizat prin Stripe.`}
            </p>
          </div>
          <button className="cal-btn primary" onClick={() => openStripe(selectedTier)} disabled={busy || (!user?.is_premium && !selectedTierAvailable)} type="button">
            {busy ? "Se deschide..." : user?.is_premium ? "Gestionează abonamentul" : "Continuă către plată"}
          </button>
        </div>

        <div className="premium-metric-grid">
          <DashboardMetric icon={<FiStar />} label="Plan curent" value={planAccessLabel(user, tiers)} sub={user?.is_premium ? "activ" : "neabonat"} />
          <DashboardMetric icon={<FiTrendingUp />} label="Super-aprecieri" value={user?.is_premium ? "3 / săptămână" : "Trubadur"} sub="pentru texte preferate" />
          <DashboardMetric icon={<FiHeadphones />} label="Audio" value={user?.has_audio_access ? "activ" : "indisponibil"} sub={quotaState.data ? `${formatNumber(quotaState.data.remaining)} caractere rămase` : "Cronicar+"} />
          <DashboardMetric icon={<FiCreditCard />} label="Facturare" value="Stripe" sub={user?.is_premium ? "portal client" : "checkout securizat"} />
        </div>

        {quotaState.data ? (
          <section className="premium-quota-panel" aria-label="Cotă audio">
            <div>
              <div className="piece-card-kicker">cotă audio</div>
              <p>
                {formatNumber(quotaState.data.used)} / {formatNumber(quotaState.data.limit)} caractere folosite
                {quotaState.data.period_end ? ` până la ${formatDateTime(quotaState.data.period_end)}` : ""}.
              </p>
            </div>
            <span className="quota-pill">{formatNumber(quotaState.data.remaining)} rămase</span>
          </section>
        ) : null}

        {status ? <div className="inline-error">{status}</div> : null}

        <div className="premium-tier-grid">
          {plansState.loading ? <div className="auth-sub">Se încarcă planurile Premium...</div> : null}
          {plansState.error ? <div className="inline-error">{plansState.error}</div> : null}
          {tiers.map((tier) => (
            <TierCard
              key={tier.key}
              tier={tier}
              user={user}
              selected={selectedTier === tier.key}
              busy={busy}
              onSelect={setSelectedTier}
              onStart={openStripe}
            />
          ))}
        </div>
      </section>
    </PageShell>
  );
}

export default function PremiumRoute({ user }) {
  return <PremiumView user={user} />;
}
