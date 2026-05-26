import { useCallback, useEffect, useRef, useState } from "react";
import { FiCheck, FiPause, FiPlay, FiSkipBack, FiSkipForward, FiUserCheck, FiUserMinus, FiUserPlus, FiX } from "react-icons/fi";
import { fetchAudioPlaylistPlayback, fetchAuthorListeningRandomAudio, fetchListeningRandomAudio, recordAudioListenSeconds } from "../api/audio.js";
import { acceptFriendRequest, deleteFriendRequest, removeFriend, sendFriendRequest } from "../api/friends.js";
import { followUser, unfollowUser } from "../api/follows.js";
import { usernameHandle } from "./format.js";
import { blogUrl } from "./paths.js";

const LISTEN_MODES = [
  { mode: "proza_scurta", label: "doar proză", ariaLabel: "Ascultă doar proză" },
  { mode: "poezie", label: "doar poezie", ariaLabel: "Ascultă doar poezie" },
  { mode: "toate", label: "de toate", ariaLabel: "Ascultă de toate" }
];
const DEFAULT_LISTEN_SOURCE = { type: "global" };

function listenSourceKey(source) {
  if (source?.type === "author") return `author:${source.username || ""}`;
  if (source?.type === "playlist") return `playlist:${source.playlistId || ""}`;
  return "global";
}

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

function TrackRelationshipActions({ track, currentUser, busy, message, onToggleFollow, onFriendAction }) {
  if (!track?.author_id || track.author_id === currentUser?.id) return null;
  const friendshipStatus = track.viewer_friendship_status || "none";
  const friendshipId = track.viewer_friendship_id || null;
  const busyFollow = busy === "follow";
  const busyFriend = Boolean(busy && busy.startsWith("friend:"));

  let friendControls = null;
  if (friendshipStatus === "incoming_pending") {
    friendControls = (
      <>
        <button className="landing-player-action primary" type="button" disabled={busyFriend || !friendshipId} onClick={() => onFriendAction("accept")} title="Acceptă cererea de prietenie">
          <FiCheck aria-hidden="true" />
          <span>Acceptă</span>
        </button>
        <button className="landing-player-action" type="button" disabled={busyFriend || !friendshipId} onClick={() => onFriendAction("delete")} title="Refuză cererea de prietenie">
          <FiX aria-hidden="true" />
          <span>Refuză</span>
        </button>
      </>
    );
  } else if (friendshipStatus === "outgoing_pending") {
    friendControls = (
      <button className="landing-player-action" type="button" disabled={busyFriend || !friendshipId} onClick={() => onFriendAction("delete")} title="Anulează cererea de prietenie">
        <FiX aria-hidden="true" />
        <span>Cerere trimisă</span>
      </button>
    );
  } else if (friendshipStatus === "friends") {
    friendControls = (
      <button className="landing-player-action" type="button" disabled={busyFriend} onClick={() => onFriendAction("remove")} title="Elimină din prieteni">
        <FiUserMinus aria-hidden="true" />
        <span>Prieteni</span>
      </button>
    );
  } else {
    friendControls = (
      <button className="landing-player-action primary" type="button" disabled={busyFriend} onClick={() => onFriendAction("send")} title="Trimite cerere de prietenie">
        <FiUserPlus aria-hidden="true" />
        <span>Adaugă prieten</span>
      </button>
    );
  }

  return (
    <div className="landing-player-relationships" aria-label="Relație cu autorul">
      <button
        className={`landing-player-action ${track.viewer_following ? "" : "primary"}`.trim()}
        type="button"
        disabled={busyFollow}
        onClick={onToggleFollow}
        aria-pressed={Boolean(track.viewer_following)}
        title={track.viewer_following ? "Nu mai urmări autorul" : "Urmărește autorul"}
      >
        {track.viewer_following ? <FiUserCheck aria-hidden="true" /> : <FiUserPlus aria-hidden="true" />}
        <span>{track.viewer_following ? "Urmărești" : "Urmărește"}</span>
      </button>
      {friendControls}
      {message ? <span className="landing-player-action-note" role="status">{message}</span> : null}
    </div>
  );
}

export function ListeningOverlay({
  open,
  audioRef,
  currentUser,
  activeMode,
  activeSource,
  playlistPosition = -1,
  playlistCount = 0,
  track,
  loading,
  error,
  playing,
  relationshipBusy,
  relationshipMessage,
  onSelectMode,
  onToggle,
  onPrevious,
  onNext,
  onClose,
  onToggleFollow,
  onFriendAction,
  canGoPrevious = false,
  canGoNext = false,
  onEnded,
  onPlay,
  onPause,
  onTimeUpdate,
  onAudioError
}) {
  if (!open) return null;
  const playlistActive = activeSource?.type === "playlist";
  const title = loading ? "Se încarcă..." : track?.title || error || "Ascultare";
  const trackHref = track?.author_username && track?.slug ? `${blogUrl(track.author_username)}/${track.slug}` : "";
  const authorHref = track?.author_username ? blogUrl(track.author_username) : "";
  const author = track?.author_username ? usernameHandle(track.author_username) : "";
  const playlistMeta = playlistActive && playlistCount
    ? `${activeSource.title || "Playlist"} · ${playlistPosition + 1}/${playlistCount}`
    : "";
  const authorMeta = activeSource?.type === "author" && activeSource.username
    ? `Ascultare de la ${usernameHandle(activeSource.username)}`
    : "";

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
        <div className="landing-player-top">
          <p className="landing-player-keepalive">
            <span>Poți lăsa browserul în fundal sau bloca telefonul.</span>
            <span>Audio-ul continuă să ruleze.</span>
          </p>
          {!playlistActive ? (
            <>
              <div className="landing-player-divider" aria-hidden="true" />
              <div className="landing-player-mode-stack" role="group" aria-label="Alege ce vrei să asculți">
                <p className="landing-player-mode-intro">Azi doresc să ascult</p>
                <div className="landing-player-mode-list">
                  {LISTEN_MODES.map((item) => {
                    const selected = activeMode === item.mode;
                    return (
                      <button
                        key={item.mode}
                        className={`landing-player-mode-link ${selected ? "active" : ""}`.trim()}
                        type="button"
                        disabled={loading}
                        aria-pressed={selected}
                        aria-label={item.ariaLabel}
                        onClick={() => onSelectMode(item.mode)}
                      >
                        <span aria-hidden="true">...</span>
                        <span>{item.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            </>
          ) : null}
        </div>
        <div className="landing-player-transport" aria-label="Controale audio">
          <button
            className="landing-player-skip"
            type="button"
            onClick={onPrevious}
            disabled={loading || !canGoPrevious}
            aria-label="Anterior"
            title="Anterior"
          >
            <FiSkipBack aria-hidden="true" />
          </button>
          <button
            className="landing-player-toggle"
            type="button"
            onClick={onToggle}
            disabled={loading}
            aria-label={playing ? "Pauză" : "Redă"}
          >
            {playing ? <FiPause aria-hidden="true" /> : <FiPlay aria-hidden="true" />}
          </button>
          <button
            className="landing-player-skip"
            type="button"
            onClick={onNext}
            disabled={loading || !canGoNext}
            aria-label="Următor"
            title="Următor"
          >
            <FiSkipForward aria-hidden="true" />
          </button>
        </div>
        <div className="landing-player-bottom">
          <div className="landing-player-now-playing">
            {playlistMeta ? <p className="landing-player-playlist-meta">{playlistMeta}</p> : null}
            {authorMeta ? <p className="landing-player-playlist-meta">{authorMeta}</p> : null}
            <h2 className="landing-player-title">
              {trackHref ? <a href={trackHref} target="_blank" rel="noreferrer">{title}</a> : title}
            </h2>
            {author ? (
              <div className="landing-player-author">
                <a href={authorHref} target="_blank" rel="noreferrer">{author}</a>
              </div>
            ) : null}
          </div>
          <TrackRelationshipActions
            track={track}
            currentUser={currentUser}
            busy={relationshipBusy}
            message={relationshipMessage}
            onToggleFollow={onToggleFollow}
            onFriendAction={onFriendAction}
          />
        </div>
      </div>
    </section>
  );
}

export function useListeningPlayer(user, authLoaded = true, onUserRefresh = null) {
  const audioRef = useRef(null);
  const activeModeRef = useRef("");
  const activeSourceRef = useRef(DEFAULT_LISTEN_SOURCE);
  const activeSourceKeyRef = useRef("global");
  const currentTrackRef = useRef(null);
  const listenHistoryRef = useRef([]);
  const listenHistoryIndexRef = useRef(-1);
  const playlistTracksRef = useRef([]);
  const playlistIndexRef = useRef(-1);
  const pendingSecondsRef = useRef(0);
  const lastAudioTimeRef = useRef(0);
  const shouldAutoplayRef = useRef(false);
  const suppressPauseFlushRef = useRef(false);
  const [listenOpen, setListenOpen] = useState(false);
  const [listenMode, setListenMode] = useState("");
  const [listenSource, setListenSource] = useState(DEFAULT_LISTEN_SOURCE);
  const [listenTrack, setListenTrack] = useState(null);
  const [listenLoading, setListenLoading] = useState(false);
  const [listenError, setListenError] = useState("");
  const [listenPlaying, setListenPlaying] = useState(false);
  const [listenAutoplayNonce, setListenAutoplayNonce] = useState(0);
  const [listenHistoryPosition, setListenHistoryPosition] = useState({ index: -1, count: 0 });
  const [playlistPosition, setPlaylistPosition] = useState(-1);
  const [playlistCount, setPlaylistCount] = useState(0);
  const [relationshipBusy, setRelationshipBusy] = useState("");
  const [relationshipMessage, setRelationshipMessage] = useState("");

  useEffect(() => {
    activeModeRef.current = listenMode;
  }, [listenMode]);

  useEffect(() => {
    currentTrackRef.current = listenTrack;
    lastAudioTimeRef.current = 0;
    setRelationshipBusy("");
    setRelationshipMessage("");
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

  const setActiveSource = useCallback((source) => {
    const nextSource = source || DEFAULT_LISTEN_SOURCE;
    activeSourceRef.current = nextSource;
    activeSourceKeyRef.current = listenSourceKey(nextSource);
    setListenSource(nextSource);
  }, []);

  const syncListenHistoryPosition = useCallback(() => {
    setListenHistoryPosition({
      index: listenHistoryIndexRef.current,
      count: listenHistoryRef.current.length
    });
  }, []);

  const resetListenHistory = useCallback(() => {
    listenHistoryRef.current = [];
    listenHistoryIndexRef.current = -1;
    setListenHistoryPosition({ index: -1, count: 0 });
  }, []);

  const rememberListenTrack = useCallback((track) => {
    if (!track || activeSourceRef.current?.type === "playlist") return;
    const nextHistory = listenHistoryRef.current.slice(0, listenHistoryIndexRef.current + 1);
    const previousTrack = nextHistory[nextHistory.length - 1];
    if (previousTrack?.audio_id !== track.audio_id) {
      nextHistory.push(track);
    }
    listenHistoryRef.current = nextHistory;
    listenHistoryIndexRef.current = nextHistory.length - 1;
    syncListenHistoryPosition();
  }, [syncListenHistoryPosition]);

  const resetPlaylistState = useCallback(() => {
    playlistTracksRef.current = [];
    playlistIndexRef.current = -1;
    setPlaylistPosition(-1);
    setPlaylistCount(0);
  }, []);

  const pauseAndResetCurrentAudio = useCallback(async () => {
    const audio = audioRef.current;
    if (audio && !audio.paused) {
      capturePlayedDelta();
      suppressPauseFlushRef.current = true;
      audio.pause();
    }
    await flushListeningSeconds();
    pendingSecondsRef.current = 0;
    lastAudioTimeRef.current = 0;
  }, [capturePlayedDelta, flushListeningSeconds]);

  const loadListenTrack = useCallback(async (mode) => {
    const targetMode = mode || activeModeRef.current || "toate";
    const source = activeSourceRef.current || DEFAULT_LISTEN_SOURCE;
    shouldAutoplayRef.current = true;
    setListenLoading(true);
    setListenError("");
    try {
      let track = null;
      if (source.type === "author") {
        track = await fetchAuthorListeningRandomAudio(source.username, targetMode);
      } else if (source.type === "playlist") {
        const index = playlistIndexRef.current >= 0 ? playlistIndexRef.current : 0;
        track = playlistTracksRef.current[index] || null;
      } else {
        track = await fetchListeningRandomAudio(targetMode);
      }
      if (!track) throw new Error("Nu există audio disponibil.");
      setListenTrack(track);
      rememberListenTrack(track);
      setListenAutoplayNonce((nonce) => nonce + 1);
    } catch (requestError) {
      shouldAutoplayRef.current = false;
      setListenTrack(null);
      setListenPlaying(false);
      setListenError(requestError.message || "Nu există audio disponibil.");
    } finally {
      setListenLoading(false);
    }
  }, [rememberListenTrack]);

  const startListening = useCallback(async (mode, source = null) => {
    if (!user?.has_audio_access) return;
    const nextSource = source || (
      activeSourceRef.current?.type === "playlist" ? DEFAULT_LISTEN_SOURCE : activeSourceRef.current || DEFAULT_LISTEN_SOURCE
    );
    const nextSourceKey = listenSourceKey(nextSource);
    setListenOpen(true);
    if (mode === activeModeRef.current && nextSourceKey === activeSourceKeyRef.current && currentTrackRef.current) return;
    await pauseAndResetCurrentAudio();
    setActiveSource(nextSource);
    resetPlaylistState();
    resetListenHistory();
    activeModeRef.current = mode;
    setListenMode(mode);
    setListenTrack(null);
    setListenError("");
    setListenPlaying(false);
    loadListenTrack(mode);
  }, [loadListenTrack, pauseAndResetCurrentAudio, resetListenHistory, resetPlaylistState, setActiveSource, user?.has_audio_access]);

  const startAuthorListening = useCallback((username) => {
    const cleanUsername = String(username || "").trim();
    if (!cleanUsername) return;
    return startListening("toate", { type: "author", username: cleanUsername });
  }, [startListening]);

  const startPlaylistListening = useCallback(async (playlist) => {
    if (!user?.has_author_audio_access || !playlist?.id) return;
    const source = {
      type: "playlist",
      playlistId: playlist.id,
      title: playlist.title || "Playlist",
    };
    setListenOpen(true);
    await pauseAndResetCurrentAudio();
    setActiveSource(source);
    resetListenHistory();
    activeModeRef.current = "toate";
    setListenMode("toate");
    setListenTrack(null);
    setListenError("");
    setListenPlaying(false);
    setListenLoading(true);
    shouldAutoplayRef.current = true;
    try {
      const data = await fetchAudioPlaylistPlayback(playlist.id);
      const tracks = Array.isArray(data?.tracks) ? data.tracks : [];
      playlistTracksRef.current = tracks;
      playlistIndexRef.current = tracks.length ? 0 : -1;
      setPlaylistCount(tracks.length);
      setPlaylistPosition(tracks.length ? 0 : -1);
      if (!tracks.length) {
        shouldAutoplayRef.current = false;
        setListenError("Playlistul nu are audio disponibil.");
        return;
      }
      setListenSource({ ...source, title: data?.title || source.title });
      activeSourceRef.current = { ...source, title: data?.title || source.title };
      setListenTrack(tracks[0]);
      setListenAutoplayNonce((nonce) => nonce + 1);
    } catch (requestError) {
      shouldAutoplayRef.current = false;
      resetPlaylistState();
      setListenError(requestError.message || "Nu am putut încărca playlistul.");
    } finally {
      setListenLoading(false);
    }
  }, [pauseAndResetCurrentAudio, resetListenHistory, resetPlaylistState, setActiveSource, user?.has_author_audio_access]);

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
    setActiveSource(DEFAULT_LISTEN_SOURCE);
    resetListenHistory();
    resetPlaylistState();
    setListenOpen(false);
    setListenMode("");
    setListenTrack(null);
    setListenError("");
    setListenPlaying(false);
  }, [capturePlayedDelta, flushListeningSeconds, resetListenHistory, resetPlaylistState, setActiveSource]);

  const toggleListeningPlayback = useCallback(async () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (!currentTrackRef.current) {
      const mode = activeModeRef.current;
      if (mode) loadListenTrack(mode);
      else setListenError("Selectează una din opțiunile de mai sus");
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

  const playKnownTrack = useCallback((track) => {
    if (!track) return;
    shouldAutoplayRef.current = true;
    setListenLoading(false);
    setListenError("");
    setListenPlaying(false);
    setListenTrack(track);
    setListenAutoplayNonce((nonce) => nonce + 1);
  }, []);

  const goToPreviousTrack = useCallback(async () => {
    if (listenLoading) return;
    if (activeSourceRef.current?.type === "playlist") {
      const previousIndex = playlistIndexRef.current - 1;
      const previousTrack = playlistTracksRef.current[previousIndex];
      if (!previousTrack) return;
      await pauseAndResetCurrentAudio();
      playlistIndexRef.current = previousIndex;
      setPlaylistPosition(previousIndex);
      playKnownTrack(previousTrack);
      return;
    }

    const previousIndex = listenHistoryIndexRef.current - 1;
    const previousTrack = listenHistoryRef.current[previousIndex];
    if (!previousTrack) return;
    await pauseAndResetCurrentAudio();
    listenHistoryIndexRef.current = previousIndex;
    syncListenHistoryPosition();
    playKnownTrack(previousTrack);
  }, [listenLoading, pauseAndResetCurrentAudio, playKnownTrack, syncListenHistoryPosition]);

  const goToNextTrack = useCallback(async () => {
    if (listenLoading) return;
    if (activeSourceRef.current?.type === "playlist") {
      const nextIndex = playlistIndexRef.current + 1;
      const nextTrack = playlistTracksRef.current[nextIndex];
      if (!nextTrack) return;
      await pauseAndResetCurrentAudio();
      playlistIndexRef.current = nextIndex;
      setPlaylistPosition(nextIndex);
      playKnownTrack(nextTrack);
      return;
    }

    const nextHistoryIndex = listenHistoryIndexRef.current + 1;
    const nextHistoryTrack = listenHistoryRef.current[nextHistoryIndex];
    await pauseAndResetCurrentAudio();
    if (nextHistoryTrack) {
      listenHistoryIndexRef.current = nextHistoryIndex;
      syncListenHistoryPosition();
      playKnownTrack(nextHistoryTrack);
      return;
    }

    const mode = activeModeRef.current;
    if (mode) {
      await loadListenTrack(mode);
    } else {
      setListenError("Selectează una din opțiunile de mai sus");
    }
  }, [listenLoading, loadListenTrack, pauseAndResetCurrentAudio, playKnownTrack, syncListenHistoryPosition]);

  const handleListenEnded = useCallback(async () => {
    capturePlayedDelta();
    await flushListeningSeconds();
    lastAudioTimeRef.current = 0;
    setListenPlaying(false);
    if (activeSourceRef.current?.type === "playlist") {
      const nextIndex = playlistIndexRef.current + 1;
      const nextTrack = playlistTracksRef.current[nextIndex];
      if (nextTrack) {
        playlistIndexRef.current = nextIndex;
        setPlaylistPosition(nextIndex);
        shouldAutoplayRef.current = true;
        setListenTrack(nextTrack);
        setListenAutoplayNonce((nonce) => nonce + 1);
      } else {
        shouldAutoplayRef.current = false;
      }
      return;
    }
    const mode = activeModeRef.current;
    if (mode) loadListenTrack(mode);
  }, [capturePlayedDelta, flushListeningSeconds, loadListenTrack]);

  const patchCurrentTrack = useCallback((patch) => {
    setListenTrack((current) => {
      if (!current) return current;
      const next = { ...current, ...patch };
      currentTrackRef.current = next;
      return next;
    });
  }, []);

  const syncFriendshipResponse = useCallback((response) => {
    patchCurrentTrack({
      viewer_friendship_status: response?.status || "none",
      viewer_friendship_id: response?.friendship?.id || response?.friendship_id || null
    });
  }, [patchCurrentTrack]);

  const toggleAuthorFollow = useCallback(async () => {
    const track = currentTrackRef.current;
    if (!track?.author_id || track.author_id === user?.id || relationshipBusy) return;
    setRelationshipBusy("follow");
    setRelationshipMessage("");
    try {
      if (track.viewer_following) {
        await unfollowUser(track.author_id);
        patchCurrentTrack({ viewer_following: false });
      } else {
        await followUser(track.author_id);
        patchCurrentTrack({ viewer_following: true });
      }
      await onUserRefresh?.();
    } catch (requestError) {
      setRelationshipMessage(requestError.message || "Nu am putut actualiza urmărirea.");
    } finally {
      setRelationshipBusy("");
    }
  }, [onUserRefresh, patchCurrentTrack, relationshipBusy, user?.id]);

  const runAuthorFriendAction = useCallback(async (kind) => {
    const track = currentTrackRef.current;
    if (!track?.author_id || track.author_id === user?.id || relationshipBusy) return;
    setRelationshipBusy(`friend:${kind}`);
    setRelationshipMessage("");
    try {
      if (kind === "send") syncFriendshipResponse(await sendFriendRequest(track.author_id));
      if (kind === "accept" && track.viewer_friendship_id) syncFriendshipResponse(await acceptFriendRequest(track.viewer_friendship_id));
      if (kind === "delete" && track.viewer_friendship_id) {
        await deleteFriendRequest(track.viewer_friendship_id);
        patchCurrentTrack({ viewer_friendship_status: "none", viewer_friendship_id: null });
      }
      if (kind === "remove") {
        await removeFriend(track.author_id);
        patchCurrentTrack({ viewer_friendship_status: "none", viewer_friendship_id: null });
      }
      await onUserRefresh?.();
    } catch (requestError) {
      setRelationshipMessage(requestError.message || "Nu am putut actualiza prietenia.");
    } finally {
      setRelationshipBusy("");
    }
  }, [onUserRefresh, patchCurrentTrack, relationshipBusy, syncFriendshipResponse, user?.id]);

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
  }, [listenAutoplayNonce, listenMode, listenTrack?.audio_id, listenTrack?.playback_url]);

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

  useEffect(() => {
    if (listenSource?.type === "playlist" && !user?.has_author_audio_access) {
      stopListening();
    }
  }, [listenSource?.type, stopListening, user?.has_author_audio_access]);

  const canListen = Boolean(user?.has_audio_access);
  const playlistActive = listenSource?.type === "playlist";
  const canGoPrevious = playlistActive ? playlistPosition > 0 : listenHistoryPosition.index > 0;
  const canGoNext = playlistActive ? playlistPosition >= 0 && playlistPosition < playlistCount - 1 : Boolean(listenMode);
  return {
    canListen,
    disabledMessage: listenAccessMessage(user, authLoaded),
    open: listenOpen,
    openListening,
    startAuthorListening,
    startPlaylistListening,
    openAuthorListening: startAuthorListening,
    openPlaylistListening: startPlaylistListening,
    overlayProps: {
      open: listenOpen,
      audioRef,
      currentUser: user,
      activeMode: listenMode,
      activeSource: listenSource,
      playlistPosition,
      playlistCount,
      track: listenTrack,
      loading: listenLoading,
      error: listenError,
      playing: listenPlaying,
      relationshipBusy,
      relationshipMessage,
      onSelectMode: startListening,
      onToggle: toggleListeningPlayback,
      onPrevious: goToPreviousTrack,
      onNext: goToNextTrack,
      onClose: stopListening,
      onToggleFollow: toggleAuthorFollow,
      onFriendAction: runAuthorFriendAction,
      canGoPrevious,
      canGoNext,
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
