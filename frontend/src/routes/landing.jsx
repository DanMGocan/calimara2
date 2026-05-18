import { useCallback, useEffect, useState } from "react";
import { GiRollingDices } from "react-icons/gi";
import { fetchLanding, postPdfUrl } from "../api/public.js";
import { PieceCol, fallbackPiece, postToPiece } from "../app/content.jsx";
import { PostPromotionMenu } from "../app/post-actions.jsx";

const LANDING_NETWORK_RETRY_DELAYS = [350, 900];
const LANDING_POST_FADE_OUT_MS = 240;
const LANDING_POST_SWAP_SETTLE_MS = 50;
const LANDING_DICE_MIN_SPIN_MS = 760;

function wait(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function fetchLandingWithNetworkRetry(category, postId = null) {
  let lastError;
  for (let attempt = 0; attempt <= LANDING_NETWORK_RETRY_DELAYS.length; attempt += 1) {
    try {
      return await fetchLanding(category, postId);
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
function AuthErrorModal({ open, errorKind, onClose }) {
  if (!open) return null;
  const inviteOnly = errorKind === "access";
  return (
    <div className="access-modal-scrim" role="presentation" onClick={onClose}>
      <section className="access-modal" role="dialog" aria-modal="true" aria-labelledby="auth-error-title" onClick={(event) => event.stopPropagation()}>
        <button className="access-modal-close" type="button" aria-label="Închide" onClick={onClose}>x</button>
        <div className="piece-card-kicker">autentificare</div>
        <h2 id="auth-error-title" className="access-modal-title">{inviteOnly ? "Acces pe bază de invitație" : "Autentificarea a eșuat"}</h2>
        <p className="access-modal-body">{inviteOnly ? "Platforma este momentan disponibilă doar pentru emailurile adăugate în lista de acces." : "Nu am putut finaliza autentificarea. Încearcă din nou."}</p>
        <button className="cal-btn primary" type="button" onClick={onClose}>Închide</button>
      </section>
    </div>
  );
}

function landingPostIdFromUrl() {
  const value = new URL(window.location.href).searchParams.get("post");
  if (!value) return null;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function clearLandingPostUrlParam() {
  const url = new URL(window.location.href);
  if (!url.searchParams.has("post")) return;
  url.searchParams.delete("post");
  window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
}

function LandingView({ user, onAuthPostIdChange, onLandingStatsChange, onFooterPostActionsChange }) {
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
  const landingPdfHref = landingPost?.owner?.username && landingPost?.slug
    ? postPdfUrl(landingPost.owner.username, landingPost.slug)
    : "#";

  const loadLanding = useCallback(async (initial = false, requestedPostId = null) => {
    const startedAt = Date.now();
    if (!initial) clearLandingPostUrlParam();
    if (!initial) setTransitioning(true);
    if (!initial) setDiceSpinning(true);
    setError("");
    try {
      const dataPromise = fetchLandingWithNetworkRetry("toate", requestedPostId);
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
    loadLanding(true, landingPostIdFromUrl());
  }, [loadLanding]);

  useEffect(() => {
    onAuthPostIdChange?.(landingPost?.id ?? null);
    return () => onAuthPostIdChange?.(null);
  }, [landingPost?.id, onAuthPostIdChange]);

  useEffect(() => {
    onLandingStatsChange?.(stats ?? null);
    return () => onLandingStatsChange?.(null);
  }, [stats, onLandingStatsChange]);

  useEffect(() => {
    if (!landingPost) {
      onFooterPostActionsChange?.(null);
      return undefined;
    }
    onFooterPostActionsChange?.({
      key: `landing:${landingPost.id}`,
      post: landingPost,
      onPostChange: setLandingPost,
      pdfHref: landingPdfHref
    });
    return () => onFooterPostActionsChange?.(null);
  }, [landingPost, landingPdfHref, onFooterPostActionsChange]);

  useEffect(() => {
    const url = new URL(window.location.href);
    const authError = url.searchParams.get("auth_error");
    if (!authError) return;
    setAuthErrorKind(authError);
    setAuthErrorOpen(true);
    url.searchParams.delete("auth_error");
    window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
  }, []);

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
        {error ? <div className="inline-error">{error}</div> : null}
      </div>
      <AuthErrorModal open={authErrorOpen} errorKind={authErrorKind} onClose={() => setAuthErrorOpen(false)} />
    </main>
  );
}

export default function LandingRoute({ user, onAuthPostIdChange, onLandingStatsChange, onFooterPostActionsChange }) {
  return (
    <LandingView
      user={user}
      onAuthPostIdChange={onAuthPostIdChange}
      onLandingStatsChange={onLandingStatsChange}
      onFooterPostActionsChange={onFooterPostActionsChange}
    />
  );
}
