import { useCallback, useEffect, useState } from "react";
import { GiRollingDices } from "react-icons/gi";
import { fetchLanding, postPdfUrl } from "../api/public.js";
import { PieceCol, fallbackPiece, postToPiece } from "../app/content.jsx";
import { AdSlot } from "../app/layout.jsx";
import { mainPath } from "../app/paths.js";
import { PostActionTools, PostPromotionMenu } from "../app/post-actions.jsx";

const LANDING_NETWORK_RETRY_DELAYS = [350, 900];
const LANDING_POST_FADE_OUT_MS = 240;
const LANDING_POST_SWAP_SETTLE_MS = 50;
const LANDING_DICE_MIN_SPIN_MS = 760;

function wait(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function fetchLandingWithNetworkRetry(category) {
  let lastError;
  for (let attempt = 0; attempt <= LANDING_NETWORK_RETRY_DELAYS.length; attempt += 1) {
    try {
      return await fetchLanding(category);
    } catch (error) {
      lastError = error;
      const canRetry = error?.status === 0 && attempt < LANDING_NETWORK_RETRY_DELAYS.length;
      if (!canRetry) throw error;
      await wait(LANDING_NETWORK_RETRY_DELAYS[attempt]);
    }
  }
  throw lastError;
}

function TitleShuffleButton({ onShuffle, disabled, spinning }) {
  return (
    <button
      className={`landing-title-dice ${spinning ? "spinning" : ""}`}
      type="button"
      aria-label="Alege un text aleatoriu"
      title="Alege un text aleatoriu"
      disabled={disabled}
      onClick={onShuffle}
    >
      <GiRollingDices aria-hidden="true" focusable="false" />
      <span className="landing-title-dice-label" aria-hidden="true">Schimbă</span>
      <span className="visually-hidden">Alege un text aleatoriu</span>
    </button>
  );
}
function Rail({ stats }) {
  if (!stats) return null;
  return (
    <aside className="rail">
      <div className="rail-stat">
        <span className="rail-label">Texte</span>
        <span className="rail-count">{Number(stats.total_posts ?? 0).toLocaleString("ro-RO")}</span>
      </div>
      <div className="rail-stat">
        <span className="rail-label">Autori</span>
        <span className="rail-count">{Number(stats.total_authors ?? 0).toLocaleString("ro-RO")}</span>
      </div>
    </aside>
  );
}
function LandingLinks() {
  const links = [
    { label: "Ce este călimara.ro?", href: mainPath("/ce-este-calimara") },
    { label: "De ce să ni te alături?", href: mainPath("/de-ce-sa-ni-te-alaturi") },
    { label: "Funcții și caracteristici", href: mainPath("/functii-si-caracteristici") }
  ];

  return (
    <aside className="landing-link-rail" aria-label="Informații călimara.ro">
      <div className="landing-link-list">
        {links.map((link, index) => (
          <a className="landing-link-row" href={link.href} key={link.href}>
            <span className="landing-link-number">{String(index + 1).padStart(2, "0")}</span>
            <span className="landing-link-label">{link.label}</span>
            <span className="landing-link-arrow" aria-hidden="true">
              <svg width="14" height="10" viewBox="0 0 14 10" fill="none">
                <path d="M1 5h11m0 0L9 1m3 4l-3 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
          </a>
        ))}
      </div>
    </aside>
  );
}

function AuthErrorModal({ open, errorKind, onClose }) {
  if (!open) return null;
  const inviteOnly = errorKind === "access";
  return (
    <div className="access-modal-scrim" role="presentation" onClick={onClose}>
      <section className="access-modal" role="dialog" aria-modal="true" aria-labelledby="auth-error-title" onClick={(event) => event.stopPropagation()}>
        <button className="access-modal-close" type="button" aria-label="Închide" onClick={onClose}>x</button>
        <div className="piece-card-kicker">autentificare</div>
        <h2 id="auth-error-title" className="access-modal-title">{inviteOnly ? "Acces pe bază de invitație" : "Autentificarea a eșuat"}</h2>
        <p className="access-modal-body">{inviteOnly ? "Platforma este momentan deschisă doar pentru emailurile adăugate în lista de acces." : "Nu am putut finaliza autentificarea. Încearcă din nou."}</p>
        <button className="cal-btn primary" type="button" onClick={onClose}>Închide</button>
      </section>
    </div>
  );
}

function LandingView({ user }) {
  const [piece, setPiece] = useState(fallbackPiece("poem"));
  const [landingPost, setLandingPost] = useState(null);
  const [stats, setStats] = useState(null);
  const [animKey, setAnimKey] = useState(0);
  const [transitioning, setTransitioning] = useState(false);
  const [diceSpinning, setDiceSpinning] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [authErrorOpen, setAuthErrorOpen] = useState(false);
  const [authErrorKind, setAuthErrorKind] = useState("");

  const loadLanding = useCallback(async (initial = false) => {
    const startedAt = Date.now();
    if (!initial) setTransitioning(true);
    if (!initial) setDiceSpinning(true);
    setError("");
    try {
      const dataPromise = fetchLandingWithNetworkRetry("toate");
      const data = initial
        ? await dataPromise
        : (await Promise.all([dataPromise, wait(LANDING_POST_FADE_OUT_MS)]))[0];
      const post = data.random_posts?.[0];
      setStats(data.stats ?? null);
      setLandingPost(post ?? null);
      setPiece(post ? postToPiece(post) : fallbackPiece("poem"));
      setAnimKey((key) => key + 1);
    } catch (requestError) {
      if (!initial) await wait(LANDING_POST_FADE_OUT_MS);
      setError(requestError.message || "Nu am putut încărca textul.");
      setLandingPost(null);
      setPiece(fallbackPiece("poem"));
      setAnimKey((key) => key + 1);
    } finally {
      setLoading(false);
      window.setTimeout(() => setTransitioning(false), initial ? 0 : LANDING_POST_SWAP_SETTLE_MS);
      if (!initial) {
        const remainingSpin = Math.max(0, LANDING_DICE_MIN_SPIN_MS - (Date.now() - startedAt));
        window.setTimeout(() => setDiceSpinning(false), remainingSpin);
      }
    }
  }, []);

  useEffect(() => {
    loadLanding(true);
  }, [loadLanding]);

  useEffect(() => {
    const url = new URL(window.location.href);
    const authError = url.searchParams.get("auth_error");
    if (!authError) return;
    setAuthErrorKind(authError);
    setAuthErrorOpen(true);
    url.searchParams.delete("auth_error");
    window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
  }, []);

  const landingPdfHref = landingPost?.owner?.username && landingPost?.slug
    ? postPdfUrl(landingPost.owner.username, landingPost.slug)
    : "#";
  const shuffleDisabled = transitioning || loading || diceSpinning;

  return (
    <main className="stage landing-stage">
      <div className={`piece-wrap ${transitioning ? "transitioning" : ""} ${landingPost?.super_likes_count > 0 ? "has-super-like" : ""}`}>
        <PieceCol
          piece={piece}
          animKey={animKey}
          titleAction={landingPost ? (
            <PostPromotionMenu post={landingPost} author={landingPost.owner} user={user} />
          ) : null}
          titlePrefix={(
            <TitleShuffleButton
              onShuffle={() => loadLanding(false)}
              disabled={shuffleDisabled}
              spinning={diceSpinning}
            />
          )}
        />
        <PostActionTools post={landingPost} user={user} onPostChange={setLandingPost} pdfHref={landingPdfHref} />
      </div>
      <div className="left-col landing-bottom-rail">
        <Rail stats={stats} />
        <LandingLinks />
        <AdSlot placement="rail" />
        {error ? <div className="inline-error">{error}</div> : null}
      </div>
      <AuthErrorModal open={authErrorOpen} errorKind={authErrorKind} onClose={() => setAuthErrorOpen(false)} />
    </main>
  );
}

export default function LandingRoute({ user }) {
  return <LandingView user={user} />;
}
