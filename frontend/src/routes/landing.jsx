import { useCallback, useEffect, useRef, useState } from "react";
import { FiPause, FiPlay } from "react-icons/fi";
import { GiPerspectiveDiceSixFacesRandom } from "react-icons/gi";
import { fetchListeningRandomAudio, recordAudioListenSeconds } from "../api/audio.js";
import { fetchLanding, postPdfUrl } from "../api/public.js";
import { PieceCol, fallbackPiece, postToPiece } from "../app/content.jsx";
import { AdSlot } from "../app/layout.jsx";
import { mainPath } from "../app/paths.js";
import { PostActionTools } from "../app/post-actions.jsx";

const LISTEN_MODES = [
  { mode: "poezie", label: "Asculta poezii" },
  { mode: "proza_scurta", label: "Asculta proza" },
  { mode: "toate", label: "Asculta de toate" }
];

function listenAccessMessage(user) {
  if (!user) return "Autentifică-te și activează Cronicar sau Rapsod pentru ascultare continuă.";
  if (!user.has_audio_access) return "Necesită abonament Cronicar sau Rapsod.";
  return "";
}

function listenEventId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return `listen-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function sendListenSecondsKeepalive(payload) {
  try {
    fetch("/api/audio/asculta/secunde", {
      method: "POST",
      credentials: "include",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload),
      keepalive: true
    }).catch(() => {});
  } catch {
    // The page is unloading; there is no useful UI recovery path here.
  }
}

function SideActions({ onShuffle, disabled, spinning }) {
  return (
    <aside className="side-col">
      <div className="side-kicker">text aleatoriu</div>
      <div className="dice-actions">
        <button
          className={`landing-dice-button ${spinning ? "spinning" : ""}`}
          type="button"
          aria-label="Alege un text aleatoriu"
          title="Alege un text aleatoriu"
          disabled={disabled}
          onClick={onShuffle}
        >
          <GiPerspectiveDiceSixFacesRandom aria-hidden="true" focusable="false" />
          <span className="visually-hidden">Alege un text aleatoriu</span>
        </button>
      </div>
    </aside>
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
    { label: "Ce este calimara.ro?", href: mainPath("/ce-este-calimara") },
    { label: "De ce sa ni te alaturi?", href: mainPath("/de-ce-sa-ni-te-alaturi") },
    { label: "Functii si Caracterisitci", href: mainPath("/functii-si-caracteristici") }
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

function ListenActions({ user, onStart }) {
  const canListen = Boolean(user?.has_audio_access);
  const disabledMessage = listenAccessMessage(user);

  return (
    <aside className="landing-listen-rail" aria-label="Ascultare audio">
      <div className="side-kicker">ascultare</div>
      <div className="landing-listen-actions">
        {LISTEN_MODES.map((item) => (
          <span className="landing-listen-tooltip" title={canListen ? item.label : disabledMessage} key={item.mode}>
            <button
              className={`landing-listen-button ${canListen ? "" : "is-disabled"}`.trim()}
              type="button"
              disabled={!canListen}
              aria-disabled={!canListen || undefined}
              onClick={() => onStart(item.mode)}
            >
              {item.label}
            </button>
          </span>
        ))}
      </div>
    </aside>
  );
}

function ListeningOverlay({
  open,
  audioRef,
  track,
  loading,
  error,
  playing,
  onToggle,
  onEnded,
  onPlay,
  onPause,
  onTimeUpdate,
  onAudioError
}) {
  if (!open) return null;
  const title = loading ? "Se încarcă..." : track?.title || error || "Ascultare";
  const author = track?.author_username ? `@${track.author_username}` : "";

  return (
    <section className="landing-listen-overlay" aria-label="Player audio">
      <audio
        ref={audioRef}
        className="landing-listen-native"
        preload="auto"
        src={track?.playback_url || undefined}
        onEnded={onEnded}
        onPlay={onPlay}
        onPause={onPause}
        onTimeUpdate={onTimeUpdate}
        onError={onAudioError}
      >
        Browserul tău nu poate reda acest fișier audio.
      </audio>
      <div className="landing-player-minimal">
        <h2 className="landing-player-title">{title}</h2>
        {author ? <div className="landing-player-author">{author}</div> : null}
        <button
          className="landing-player-toggle"
          type="button"
          onClick={onToggle}
          disabled={loading || (!track && !error)}
          aria-label={playing ? "Pauză" : "Redă"}
        >
          {playing ? <FiPause aria-hidden="true" /> : <FiPlay aria-hidden="true" />}
        </button>
      </div>
    </section>
  );
}

function AuthErrorModal({ open, onClose }) {
  if (!open) return null;
  return (
    <div className="access-modal-scrim" role="presentation" onClick={onClose}>
      <section className="access-modal" role="dialog" aria-modal="true" aria-labelledby="auth-error-title" onClick={(event) => event.stopPropagation()}>
        <button className="access-modal-close" type="button" aria-label="Închide" onClick={onClose}>x</button>
        <div className="piece-card-kicker">autentificare</div>
        <h2 id="auth-error-title" className="access-modal-title">Autentificarea a eșuat</h2>
        <p className="access-modal-body">Nu am putut finaliza autentificarea cu Google. Încearcă din nou.</p>
        <button className="cal-btn primary" type="button" onClick={onClose}>Închide</button>
      </section>
    </div>
  );
}

function LandingView({ user }) {
  const audioRef = useRef(null);
  const activeModeRef = useRef("");
  const currentTrackRef = useRef(null);
  const pendingSecondsRef = useRef(0);
  const lastAudioTimeRef = useRef(0);
  const shouldAutoplayRef = useRef(false);
  const [piece, setPiece] = useState(fallbackPiece("poem"));
  const [landingPost, setLandingPost] = useState(null);
  const [stats, setStats] = useState(null);
  const [animKey, setAnimKey] = useState(0);
  const [transitioning, setTransitioning] = useState(false);
  const [diceSpinning, setDiceSpinning] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [authErrorOpen, setAuthErrorOpen] = useState(false);
  const [listenMode, setListenMode] = useState("");
  const [listenTrack, setListenTrack] = useState(null);
  const [listenLoading, setListenLoading] = useState(false);
  const [listenError, setListenError] = useState("");
  const [listenPlaying, setListenPlaying] = useState(false);

  useEffect(() => {
    activeModeRef.current = listenMode;
  }, [listenMode]);

  useEffect(() => {
    currentTrackRef.current = listenTrack;
    lastAudioTimeRef.current = 0;
  }, [listenTrack?.audio_id]);

  const capturePlayedDelta = useCallback(() => {
    const audio = audioRef.current;
    const track = currentTrackRef.current;
    if (!audio || !track) return;
    const current = audio.currentTime;
    const last = lastAudioTimeRef.current;
    if (Number.isFinite(current) && Number.isFinite(last)) {
      const delta = current - last;
      if (delta > 0) {
        pendingSecondsRef.current += delta;
      }
    }
    lastAudioTimeRef.current = Number.isFinite(current) ? current : 0;
  }, []);

  const flushListeningSeconds = useCallback((keepalive = false) => {
    capturePlayedDelta();
    const track = currentTrackRef.current;
    const mode = activeModeRef.current || "toate";
    let seconds = Math.floor(pendingSecondsRef.current);
    if (!track || seconds <= 0) return Promise.resolve();

    pendingSecondsRef.current -= seconds;
    const payloads = [];
    while (seconds > 0) {
      const batchSeconds = Math.min(60, seconds);
      payloads.push({
        event_id: listenEventId(),
        audio_id: track.audio_id,
        seconds: batchSeconds,
        mode
      });
      seconds -= batchSeconds;
    }

    if (keepalive) {
      payloads.forEach(sendListenSecondsKeepalive);
      return Promise.resolve();
    }

    return Promise.all(
      payloads.map((payload) => (
        recordAudioListenSeconds({
          eventId: payload.event_id,
          audioId: payload.audio_id,
          seconds: payload.seconds,
          mode: payload.mode
        }).catch(() => {})
      ))
    );
  }, [capturePlayedDelta]);

  const loadListenTrack = useCallback(async (mode) => {
    const targetMode = mode || activeModeRef.current || "toate";
    shouldAutoplayRef.current = true;
    setListenLoading(true);
    setListenError("");
    try {
      const track = await fetchListeningRandomAudio(targetMode);
      setListenTrack(track);
    } catch (requestError) {
      shouldAutoplayRef.current = false;
      setListenTrack(null);
      setListenPlaying(false);
      setListenError(requestError.message || "Nu există audio disponibil.");
    } finally {
      setListenLoading(false);
    }
  }, []);

  const startListening = useCallback(async (mode) => {
    if (!user?.has_audio_access) return;
    await flushListeningSeconds();
    pendingSecondsRef.current = 0;
    lastAudioTimeRef.current = 0;
    activeModeRef.current = mode;
    setListenMode(mode);
    setListenTrack(null);
    setListenError("");
    setListenPlaying(false);
    loadListenTrack(mode);
  }, [flushListeningSeconds, loadListenTrack, user?.has_audio_access]);

  const stopListening = useCallback(() => {
    flushListeningSeconds(true);
    const audio = audioRef.current;
    if (audio) audio.pause();
    pendingSecondsRef.current = 0;
    lastAudioTimeRef.current = 0;
    shouldAutoplayRef.current = false;
    activeModeRef.current = "";
    setListenMode("");
    setListenTrack(null);
    setListenError("");
    setListenPlaying(false);
  }, [flushListeningSeconds]);

  const toggleListeningPlayback = useCallback(async () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (!currentTrackRef.current) {
      loadListenTrack(activeModeRef.current || "toate");
      return;
    }
    if (!audio.paused) {
      audio.pause();
      return;
    }
    setListenError("");
    try {
      await audio.play();
    } catch {
      setListenPlaying(false);
      setListenError("Audio nu poate fi redat.");
    }
  }, [loadListenTrack]);

  const handleListenEnded = useCallback(async () => {
    capturePlayedDelta();
    await flushListeningSeconds();
    lastAudioTimeRef.current = 0;
    setListenPlaying(false);
    const mode = activeModeRef.current;
    if (mode) loadListenTrack(mode);
  }, [capturePlayedDelta, flushListeningSeconds, loadListenTrack]);

  useEffect(() => {
    if (!listenMode || !listenTrack?.playback_url) return;
    const audio = audioRef.current;
    if (!audio || !shouldAutoplayRef.current) return;
    lastAudioTimeRef.current = 0;
    audio.load();
    audio.play().catch(() => {
      setListenPlaying(false);
      setListenError("Apasă Redă pentru a porni audio.");
    });
  }, [listenMode, listenTrack?.audio_id, listenTrack?.playback_url]);

  useEffect(() => {
    if (!listenMode) return undefined;
    const interval = window.setInterval(() => {
      if (!audioRef.current?.paused) flushListeningSeconds();
    }, 10000);
    return () => window.clearInterval(interval);
  }, [flushListeningSeconds, listenMode]);

  useEffect(() => {
    if (!listenMode) return undefined;
    const onKeyDown = (event) => {
      if (event.key === "Escape") stopListening();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [listenMode, stopListening]);

  useEffect(() => {
    const onPageHide = () => {
      if (activeModeRef.current) flushListeningSeconds(true);
    };
    const onVisibilityChange = () => {
      if (document.visibilityState === "hidden" && activeModeRef.current) {
        flushListeningSeconds(true);
      }
    };
    window.addEventListener("pagehide", onPageHide);
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      window.removeEventListener("pagehide", onPageHide);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [flushListeningSeconds]);

  const loadLanding = useCallback(async (initial = false) => {
    const startedAt = Date.now();
    if (!initial) setTransitioning(true);
    if (!initial) setDiceSpinning(true);
    setError("");
    try {
      const data = await fetchLanding("toate");
      const post = data.random_posts?.[0];
      setStats(data.stats ?? null);
      setLandingPost(post ?? null);
      setPiece(post ? postToPiece(post) : fallbackPiece("poem"));
      setAnimKey((key) => key + 1);
    } catch (requestError) {
      setError(requestError.message || "Nu am putut încărca textul.");
      setLandingPost(null);
      setPiece(fallbackPiece("poem"));
      setAnimKey((key) => key + 1);
    } finally {
      setLoading(false);
      window.setTimeout(() => setTransitioning(false), initial ? 0 : 80);
      if (!initial) {
        const remainingSpin = Math.max(0, 520 - (Date.now() - startedAt));
        window.setTimeout(() => setDiceSpinning(false), remainingSpin);
      }
    }
  }, []);

  useEffect(() => {
    loadLanding(true);
  }, [loadLanding]);

  useEffect(() => {
    const url = new URL(window.location.href);
    if (url.searchParams.get("auth_error") !== "google") return;
    setAuthErrorOpen(true);
    url.searchParams.delete("auth_error");
    window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
  }, []);

  const landingPdfHref = landingPost?.owner?.username && landingPost?.slug
    ? postPdfUrl(landingPost.owner.username, landingPost.slug)
    : "#";

  return (
    <main className="stage">
      <div className="left-col">
        <SideActions
          onShuffle={() => loadLanding(false)}
          disabled={transitioning || loading || diceSpinning}
          spinning={diceSpinning}
        />
        <Rail stats={stats} />
        <ListenActions user={user} onStart={startListening} />
        <LandingLinks />
        <AdSlot placement="rail" />
        {error ? <div className="inline-error">{error}</div> : null}
      </div>
      <div className={`piece-wrap ${transitioning ? "transitioning" : ""} ${landingPost?.super_likes_count > 0 ? "has-super-like" : ""}`}>
        <PieceCol piece={piece} animKey={animKey} />
        <PostActionTools post={landingPost} user={user} onPostChange={setLandingPost} pdfHref={landingPdfHref} />
      </div>
      <ListeningOverlay
        open={Boolean(listenMode)}
        audioRef={audioRef}
        track={listenTrack}
        loading={listenLoading}
        error={listenError}
        playing={listenPlaying}
        onToggle={toggleListeningPlayback}
        onEnded={handleListenEnded}
        onPlay={() => {
          lastAudioTimeRef.current = audioRef.current?.currentTime || 0;
          setListenPlaying(true);
        }}
        onPause={() => {
          capturePlayedDelta();
          flushListeningSeconds();
          setListenPlaying(false);
        }}
        onTimeUpdate={capturePlayedDelta}
        onAudioError={() => {
          if (!listenTrack) return;
          setListenPlaying(false);
          setListenError("Audio nu poate fi redat.");
        }}
      />
      <AuthErrorModal open={authErrorOpen} onClose={() => setAuthErrorOpen(false)} />
    </main>
  );
}

export default function LandingRoute({ user }) {
  return <LandingView user={user} />;
}
