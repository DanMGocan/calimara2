import { useEffect, useMemo, useState } from "react";
import { FiCheckCircle, FiCopy, FiCreditCard, FiEdit3, FiGift, FiHeadphones, FiStar, FiTrendingUp, FiUsers } from "react-icons/fi";
import { SiBuymeacoffee } from "react-icons/si";
import { fetchAudioConversionQuota } from "../api/audio.js";
import { fetchPremiumPlans, openPremiumPortal, startPremiumCheckout } from "../api/premium.js";
import { fetchMyReferrals } from "../api/referrals.js";
import { fetchDiacriticsQuota } from "../api/writing.js";
import { useAuthModal } from "../app/auth-modal.jsx";
import { PROFILE_TIER_BADGES } from "../app/constants.js";
import { formatDateTime, formatNumber } from "../app/format.js";
import { useAsync } from "../app/hooks.js";
import { PageShell } from "../app/layout.jsx";
import { mainPath } from "../app/paths.js";

const TIER_RANK = {
  free: 0,
  trubadur: 1,
  cronicar: 2,
  rapsod: 3
};
const SUPER_LIKE_MONTHLY_QUOTAS = {
  free: 1,
  trubadur: 3,
  cronicar: 4,
  rapsod: 5
};
const BUY_ME_A_COFFEE_URL = "https://www.buymeacoffee.com/danmihaig";

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

function superLikeQuotaLabel(user) {
  const tier = user?.is_premium ? user.premium_tier : "free";
  const quota = SUPER_LIKE_MONTHLY_QUOTAS[tier] ?? SUPER_LIKE_MONTHLY_QUOTAS.trubadur;
  return `${formatNumber(quota)} / lună`;
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
  const isFree = tier.key === "free";
  const active = isFree ? Boolean(user && !user.is_premium) : Boolean(user?.is_premium && user.premium_tier === tier.key);
  const included = Boolean(user?.is_premium && TIER_RANK[user.premium_tier] >= TIER_RANK[tier.key]);
  const unavailable = !isFree && !tier.available && !user?.is_premium;
  const disabled = isFree || busy || Boolean(user?.is_premium) || unavailable;
  const tierBadge = PROFILE_TIER_BADGES[tier.key] || PROFILE_TIER_BADGES.trubadur;
  const buttonLabel = isFree
    ? user?.is_premium ? "Inclus în planul tău" : user ? "Plan activ" : "Plan gratuit"
    : unavailable
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
          if (isFree) return;
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

function CoffeeSupportPanel() {
  return (
    <section className="premium-coffee-panel" aria-label="Sprijină Călimara cu o cafea">
      <div>
        <div className="piece-card-kicker">fără abonament</div>
        <h2>Te-ai săturat de subscripții și abonamente?</h2>
        <p>
          Înțeleg. Așa și eu. Dacă nu mai vrei încă o subscripție, sunt fericit să îmi cumperi o cafea.
          Nu vine cu niciun beneficiu, în afară de un mic trofeu pe site, dar ajută cu întreținerea site-ului
          și cu întreținerea unui stil de viață luxuriant pentru mine: ipoteca și factura la curent.
        </p>
        <span className="premium-coffee-signature">Dan</span>
      </div>
      <a className="cal-btn primary premium-coffee-link" href={BUY_ME_A_COFFEE_URL} target="_blank" rel="noreferrer">
        <SiBuymeacoffee aria-hidden="true" />
        Cumpără-mi o cafea
      </a>
    </section>
  );
}

function ReferralPanel({ state, copied, onCopy }) {
  if (state.loading) {
    return (
      <section className="premium-referral-panel" aria-label="Recomandări">
        <div className="piece-card-kicker">recomandări</div>
        <p>Se încarcă linkul de recomandare...</p>
      </section>
    );
  }
  if (state.error) {
    return <div className="inline-error">{state.error}</div>;
  }
  const data = state.data;
  if (!data) return null;
  const referralUrl = typeof window === "undefined"
    ? data.referral_url
    : `${window.location.origin}${data.referral_path}`;
  const recent = (data.referrals || []).slice(0, 4);
  return (
    <section className="premium-referral-panel" aria-label="Recomandări">
      <div className="premium-referral-copy">
        <div>
          <div className="piece-card-kicker">recomandări</div>
          <h2>Invită autori, primești Trubadur</h2>
          <p>
            Când un cont creat cu linkul tău câștigă {formatNumber(data.threshold_gologani)} Gologani,
            primești {formatNumber(data.reward_days)} zile de Trubadur.
          </p>
        </div>
        <div className="premium-referral-link-row">
          <input className="cal-input" value={referralUrl} readOnly aria-label="Link de recomandare" />
          <button className="cal-btn" type="button" onClick={() => onCopy(referralUrl)}>
            <FiCopy aria-hidden="true" />
            {copied ? "Copiat" : "Copiază"}
          </button>
          <a className="cal-btn" href={mainPath("/invitatii")}>Detalii</a>
        </div>
      </div>
      <div className="premium-referral-stats">
        <DashboardMetric icon={<FiUsers />} label="Autori aduși" value={formatNumber(data.referred_count)} sub={`${formatNumber(data.pending_count)} în progres`} />
        <DashboardMetric icon={<FiGift />} label="Recompense" value={formatNumber(data.rewarded_count)} sub={`${formatNumber(data.reward_days)} zile fiecare`} />
      </div>
      {recent.length ? (
        <div className="premium-referral-list">
          {recent.map((item) => (
            <div className="premium-referral-row" key={item.user_id}>
              <span>{item.username}</span>
              <strong>{formatNumber(item.earned_gologani)} / {formatNumber(data.threshold_gologani)} Gologani</strong>
              <small>{item.rewarded_at ? "recompensă acordată" : "în progres"}</small>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function PremiumView({ user }) {
  const { openAuthModal } = useAuthModal();
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [selectedTier, setSelectedTier] = useState(user?.premium_tier && user.premium_tier !== "free" ? user.premium_tier : "trubadur");
  const [copiedReferral, setCopiedReferral] = useState(false);
  const plansState = useAsync(fetchPremiumPlans, []);
  const tiers = plansState.data || [];
  const selectedTierDetails = useMemo(() => tierByKey(selectedTier, tiers), [selectedTier, tiers]);
  const selectedTierAvailable = Boolean(selectedTierDetails?.available);
  const selectedTierName = selectedTierDetails?.name || tierName(selectedTier, tiers);
  const activeTier = user?.is_premium ? tierByKey(user.premium_tier, tiers) : null;
  const audioQuotaState = useAsync(
    () => (user ? fetchAudioConversionQuota() : Promise.resolve(null)),
    [user?.id, user?.premium_tier, user?.premium_until]
  );
  const diacriticsQuotaState = useAsync(
    () => (user ? fetchDiacriticsQuota() : Promise.resolve(null)),
    [user?.id, user?.premium_tier, user?.premium_until]
  );
  const referralsState = useAsync(
    () => (user ? fetchMyReferrals() : Promise.resolve(null)),
    [user?.id, user?.premium_until]
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
      openAuthModal?.();
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

  const copyReferralLink = async (url) => {
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      setCopiedReferral(true);
      window.setTimeout(() => setCopiedReferral(false), 1800);
    } catch {
      setStatus("Nu am putut copia linkul automat.");
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

        <CoffeeSupportPanel />

        {user ? <ReferralPanel state={referralsState} copied={copiedReferral} onCopy={copyReferralLink} /> : null}

        <div className="premium-metric-grid">
          <DashboardMetric icon={<FiStar />} label="Plan curent" value={planAccessLabel(user, tiers)} sub={user?.is_premium ? "activ" : "neabonat"} />
          <DashboardMetric icon={<FiTrendingUp />} label="Super-aprecieri" value={superLikeQuotaLabel(user)} sub="pentru texte preferate" />
          <DashboardMetric icon={<FiEdit3 />} label="Diacritice" value={diacriticsQuotaState.data ? `${formatNumber(diacriticsQuotaState.data.remaining)} rămase` : "activ"} sub="caractere lunar" />
          <DashboardMetric icon={<FiHeadphones />} label="Audio" value={audioQuotaState.data?.limit ? "cotă activă" : user?.has_audio_access ? "activ" : "indisponibil"} sub={audioQuotaState.data ? `${formatNumber(audioQuotaState.data.remaining)} caractere rămase` : "conversie text-audio"} />
          <DashboardMetric icon={<FiCreditCard />} label="Facturare" value="Stripe" sub={user?.is_premium ? "portal client" : "checkout securizat"} />
        </div>

        {diacriticsQuotaState.data ? (
          <section className="premium-quota-panel" aria-label="Cotă Diacritice">
            <div>
              <div className="piece-card-kicker">cotă diacritice</div>
              <p>
                {formatNumber(diacriticsQuotaState.data.used)} / {formatNumber(diacriticsQuotaState.data.limit)} caractere folosite
                {diacriticsQuotaState.data.period_end ? ` până la ${formatDateTime(diacriticsQuotaState.data.period_end)}` : ""}.
              </p>
            </div>
            <span className="quota-pill">{formatNumber(diacriticsQuotaState.data.remaining)} rămase</span>
          </section>
        ) : null}

        {audioQuotaState.data ? (
          <section className="premium-quota-panel" aria-label="Cotă audio">
            <div>
              <div className="piece-card-kicker">cotă audio</div>
              <p>
                {formatNumber(audioQuotaState.data.used)} / {formatNumber(audioQuotaState.data.limit)} caractere folosite
                {audioQuotaState.data.period_end ? ` până la ${formatDateTime(audioQuotaState.data.period_end)}` : ""}.
              </p>
            </div>
            <span className="quota-pill">{formatNumber(audioQuotaState.data.remaining)} rămase</span>
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
