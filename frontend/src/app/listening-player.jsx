import { useCallback, useEffect, useRef, useState } from "react";
import { FiPause, FiPlay, FiX } from "react-icons/fi";
import { fetchListeningRandomAudio, recordAudioListenSeconds } from "../api/audio.js";

const LISTEN_MODES = [
  { mode: "poezie", label: "Asculta poezii" },
  { mode: "proza_scurta", label: "Asculta proza" },
  { mode: "toate", label: "Asculta de toate" }
];

export function listenAccessMessage(user, authLoaded = true) {
  if (!authLoaded) return "Se verifică sesiunea...";
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

export function ListeningOverlay({
  open,
  audioRef,
  activeMode,
  track,
  loading,
  error,
  playing,
  onSelectMode,
  onToggle,
  onClose,
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
    <section className="landing-listen-overlay" id="landing-listen-player" aria-label="Player audio">
      <button className="landing-player-close" type="button" aria-label="Închide playerul audio" onClick={onClose}>
        <FiX aria-hidden="true" />
      </button>
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
        <div className="landing-player-mode-grid" role="group" aria-label="Alege ce vrei să asculți">
          {LISTEN_MODES.map((item) => {
            const selected = activeMode === item.mode;
            return (
              <button
                className={`landing-player-mode ${selected ? "active" : ""}`.trim()}
                type="button"
                disabled={loading}
                aria-pressed={selected}
                onClick={() => onSelectMode(item.mode)}
                key={item.mode}
              >
                {item.label}
              </button>
            );
          })}
        </div>
        <button
          className="landing-player-toggle"
          type="button"
          onClick={onToggle}
          disabled={loading || (!track && !error && !activeMode)}
          aria-label={playing ? "Pauză" : "Redă"}
        >
          {playing ? <FiPause aria-hidden="true" /> : <FiPlay aria-hidden="true" />}
        </button>
      </div>
    </section>
  );
}

export function useListeningPlayer(user, authLoaded = true) {
  const audioRef = useRef(null);
  const activeModeRef = useRef("");
  const currentTrackRef = useRef(null);
  const pendingSecondsRef = useRef(0);
  const lastAudioTimeRef = useRef(0);
  const shouldAutoplayRef = useRef(false);
  const suppressPauseFlushRef = useRef(false);
  const [listenOpen, setListenOpen] = useState(false);
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

  const openListening = useCallback(() => {
    if (!user?.has_audio_access) return;
    setListenOpen(true);
  }, [user?.has_audio_access]);

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
    setListenOpen(true);
    if (mode === activeModeRef.current && currentTrackRef.current) return;
    const audio = audioRef.current;
    if (audio && !audio.paused) {
      capturePlayedDelta();
      suppressPauseFlushRef.current = true;
      audio.pause();
    }
    await flushListeningSeconds();
    pendingSecondsRef.current = 0;
    lastAudioTimeRef.current = 0;
    activeModeRef.current = mode;
    setListenMode(mode);
    setListenTrack(null);
    setListenError("");
    setListenPlaying(false);
    loadListenTrack(mode);
  }, [capturePlayedDelta, flushListeningSeconds, loadListenTrack, user?.has_audio_access]);

  const stopListening = useCallback(() => {
    const audio = audioRef.current;
    if (audio && !audio.paused) {
      capturePlayedDelta();
      suppressPauseFlushRef.current = true;
      audio.pause();
    }
    flushListeningSeconds(true);
    pendingSecondsRef.current = 0;
    lastAudioTimeRef.current = 0;
    shouldAutoplayRef.current = false;
    activeModeRef.current = "";
    setListenOpen(false);
    setListenMode("");
    setListenTrack(null);
    setListenError("");
    setListenPlaying(false);
  }, [capturePlayedDelta, flushListeningSeconds]);

  const toggleListeningPlayback = useCallback(async () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (!currentTrackRef.current) {
      const mode = activeModeRef.current;
      if (mode) loadListenTrack(mode);
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
    if (!listenOpen) return undefined;
    const onKeyDown = (event) => {
      if (event.key === "Escape") stopListening();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [listenOpen, stopListening]);

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

  useEffect(() => {
    if (!user?.has_audio_access && (listenOpen || listenMode)) {
      stopListening();
    }
  }, [listenMode, listenOpen, stopListening, user?.has_audio_access]);

  const canListen = Boolean(user?.has_audio_access);
  return {
    canListen,
    disabledMessage: listenAccessMessage(user, authLoaded),
    open: listenOpen,
    openListening,
    overlayProps: {
      open: listenOpen,
      audioRef,
      activeMode: listenMode,
      track: listenTrack,
      loading: listenLoading,
      error: listenError,
      playing: listenPlaying,
      onSelectMode: startListening,
      onToggle: toggleListeningPlayback,
      onClose: stopListening,
      onEnded: handleListenEnded,
      onPlay: () => {
        lastAudioTimeRef.current = audioRef.current?.currentTime || 0;
        setListenPlaying(true);
      },
      onPause: () => {
        if (suppressPauseFlushRef.current) {
          suppressPauseFlushRef.current = false;
          setListenPlaying(false);
          return;
        }
        capturePlayedDelta();
        flushListeningSeconds();
        setListenPlaying(false);
      },
      onTimeUpdate: capturePlayedDelta,
      onAudioError: () => {
        if (!listenTrack) return;
        setListenPlaying(false);
        setListenError("Audio nu poate fi redat.");
      }
    }
  };
}
