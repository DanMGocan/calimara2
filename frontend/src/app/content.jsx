import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FaPause, FaPlay } from "react-icons/fa";
import { recordAudioListenSeconds } from "../api/audio.js";
import { POEMS, STORIES } from "../content.js";
import { MODERATING_STATUSES, TEXT_MODERATION_MESSAGE } from "./constants.js";
import { categoryLabel, formatAudioTime, formatDateTime, htmlToText, moderationLabel, slotLabel, hasHtml, usernameHandle } from "./format.js";
import { blogUrl } from "./paths.js";
import { profileTierBadge } from "./profile-links.jsx";

export function RichTextContent({ html, className = "" }) {
  const classes = `rich-text-content ${className}`.trim();
  if (hasHtml(html)) {
    return <div className={classes} dangerouslySetInnerHTML={{ __html: html || "" }} />;
  }

  const text = htmlToText(html);
  if (!text) return <div className={classes} />;

  return (
    <div className={classes}>
      {text.split(/\n{2,}/).map((block, index) => (
        <p key={index}>
          {block.split("\n").map((line, lineIndex) => (
            <Fragment key={`${index}-${lineIndex}`}>
              {lineIndex ? <br /> : null}
              {line}
            </Fragment>
          ))}
        </p>
      ))}
    </div>
  );
}

const LISTEN_RECORD_MODES = new Set(["poezie", "proza_scurta", "toate"]);

function listenRecordEventId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return `inline-listen-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function normalizeListenRecordMode(mode) {
  return LISTEN_RECORD_MODES.has(mode) ? mode : "toate";
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

export function CompactAudioPlayer({
  src,
  audioId = null,
  listenMode = "toate",
  downloadUrl,
  className = "",
  showDownload = true,
  downloadLabel = "Descarcă",
  disabledTitle = ""
}) {
  const audioRef = useRef(null);
  const pendingListenSecondsRef = useRef(0);
  const lastAudioTimeRef = useRef(0);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState("");
  const disabled = !src;
  const recordingEnabled = Boolean(src && audioId);
  const normalizedListenMode = normalizeListenRecordMode(listenMode);

  useEffect(() => {
    const audio = audioRef.current;
    setPlaying(false);
    setCurrentTime(0);
    setDuration(0);
    setError("");
    pendingListenSecondsRef.current = 0;
    lastAudioTimeRef.current = 0;
    if (audio) {
      audio.pause();
      audio.currentTime = 0;
      if (src) audio.load();
    }
  }, [audioId, src]);

  const capturePlayedDelta = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const current = audio.currentTime;
    const last = lastAudioTimeRef.current;
    if (recordingEnabled && Number.isFinite(current) && Number.isFinite(last)) {
      const delta = current - last;
      if (delta > 0) {
        pendingListenSecondsRef.current += delta;
      }
    }
    lastAudioTimeRef.current = Number.isFinite(current) ? current : 0;
  }, [recordingEnabled]);

  const flushListenSeconds = useCallback((keepalive = false) => {
    capturePlayedDelta();
    const numericAudioId = Number(audioId);
    let seconds = Math.floor(pendingListenSecondsRef.current);
    if (!recordingEnabled || !Number.isFinite(numericAudioId) || numericAudioId <= 0 || seconds <= 0) {
      return Promise.resolve();
    }

    pendingListenSecondsRef.current -= seconds;
    const payloads = [];
    while (seconds > 0) {
      const batchSeconds = Math.min(60, seconds);
      payloads.push({
        event_id: listenRecordEventId(),
        audio_id: numericAudioId,
        seconds: batchSeconds,
        mode: normalizedListenMode
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
  }, [audioId, capturePlayedDelta, normalizedListenMode, recordingEnabled]);

  useEffect(() => {
    if (!recordingEnabled) return undefined;
    const interval = window.setInterval(() => {
      if (!audioRef.current?.paused) void flushListenSeconds();
    }, 10000);
    return () => window.clearInterval(interval);
  }, [flushListenSeconds, recordingEnabled]);

  useEffect(() => {
    if (!recordingEnabled) return undefined;
    const onPageHide = () => {
      void flushListenSeconds(true);
    };
    const onVisibilityChange = () => {
      if (document.visibilityState === "hidden") {
        void flushListenSeconds(true);
      }
    };
    window.addEventListener("pagehide", onPageHide);
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      void flushListenSeconds(true);
      window.removeEventListener("pagehide", onPageHide);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [flushListenSeconds, recordingEnabled]);

  const togglePlayback = async () => {
    const audio = audioRef.current;
    if (!audio || !src) return;
    setError("");
    if (playing) {
      audio.pause();
      return;
    }
    try {
      await audio.play();
    } catch {
      setError("Audio nu poate fi redat.");
    }
  };

  const syncDuration = () => {
    const audio = audioRef.current;
    setDuration(audio && Number.isFinite(audio.duration) ? audio.duration : 0);
  };
  const timeLabel = `${formatAudioTime(currentTime)} / ${formatAudioTime(duration)}`;
  const actionLabel = playing ? "Pauză" : "Redă";

  return (
    <div
      className={`compact-audio-player ${disabled ? "is-disabled" : ""} ${className}`.trim()}
      title={disabled ? disabledTitle : undefined}
      aria-disabled={disabled || undefined}
    >
      <audio
        ref={audioRef}
        className="compact-audio-native"
        preload="metadata"
        src={src || undefined}
        onLoadedMetadata={syncDuration}
        onDurationChange={syncDuration}
        onTimeUpdate={(event) => {
          setCurrentTime(event.currentTarget.currentTime);
          capturePlayedDelta();
        }}
        onPlay={() => {
          lastAudioTimeRef.current = audioRef.current?.currentTime || 0;
          setPlaying(true);
        }}
        onPause={() => {
          capturePlayedDelta();
          void flushListenSeconds();
          setPlaying(false);
        }}
        onEnded={() => {
          capturePlayedDelta();
          void flushListenSeconds();
          setPlaying(false);
          setCurrentTime(duration);
        }}
        onError={() => {
          if (!src) return;
          setPlaying(false);
          setError("Audio nu poate fi redat.");
        }}
      >
        Browserul tău nu poate reda acest fișier audio.
      </audio>
      <button className="compact-audio-play" type="button" onClick={togglePlayback} disabled={disabled} aria-label={`${actionLabel} audio (${timeLabel})`}>
        <span className="compact-audio-action-label" aria-hidden="true">
          {playing ? <FaPause className="compact-audio-play-icon" /> : <FaPlay className="compact-audio-play-icon" />}
        </span>
        <span className="compact-audio-time" aria-hidden="true">{timeLabel}</span>
      </button>
      {showDownload && src ? (
        <a className="compact-audio-download" href={downloadUrl || src} download>
          {downloadLabel}
        </a>
      ) : null}
      {error ? <span className="compact-audio-error">{error}</span> : null}
    </div>
  );
}
export function postToPiece(post) {
  const authorUrl = post.owner ? blogUrl(post.owner.username) : "";
  const postUrl = authorUrl && post.slug ? `${authorUrl}/${post.slug}` : "#";
  return {
    title: post.title,
    author: post.owner?.username ?? "anonim",
    authorUser: post.owner ?? null,
    authorUrl,
    year: formatDateTime(post.created_at),
    categoryLabel: post.category_name ?? categoryLabel(post.category),
    body: htmlToText(post.content),
    contentHtml: post.content,
    postUrl,
    explanatoryNote: post.explanatory_note || ""
  };
}
export function postHref(post) {
  return post?.owner ? `${blogUrl(post.owner.username)}/${post.slug}` : post?.url || "#";
}
export function AuthorLink({ user, username, children, className = "author-link" }) {
  const name = user?.username || username;
  if (!name) return children ?? null;
  const hasTierData = Boolean(user && ("is_premium" in user || "premium_tier" in user));
  const tierBadge = hasTierData ? profileTierBadge(user) : null;
  const classes = [className, tierBadge?.className].filter(Boolean).join(" ");
  const label = children ?? usernameHandle(name);
  const displayLabel = typeof label === "string" && label.trim().replace(/^@/, "") === name
    ? usernameHandle(name)
    : label;
  return (
    <a className={classes} href={blogUrl(name)} title={tierBadge ? `${usernameHandle(name)} · ${tierBadge.label} (${tierBadge.tone})` : undefined}>
      <span className="author-link-name">{displayLabel}</span>
      {tierBadge ? <span className={`author-tier-badge ${tierBadge.className}`}>{tierBadge.label}</span> : null}
    </a>
  );
}
export function PostTitleLink({ post, children, className = "post-title-link" }) {
  const href = postHref(post);
  if (!href || href === "#") return children ?? post?.title ?? null;
  return <a className={className} href={href}>{children ?? post?.title}</a>;
}
function authorDomainHandle(username) {
  const name = String(username || "").trim();
  return name ? `${usernameHandle(name)}.calimara.ro` : "";
}
function ExplanatoryNoteBubble({ note }) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const cleanNote = String(note || "").trim();

  useEffect(() => {
    setOpen(false);
  }, [cleanNote]);

  useEffect(() => {
    if (!open) return undefined;
    const onPointerDown = (event) => {
      if (wrapRef.current?.contains(event.target)) return;
      setOpen(false);
    };
    const onKeyDown = (event) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  if (!cleanNote) return null;

  return (
    <span className="piece-note-wrap" ref={wrapRef}>
      <button
        className="piece-note-trigger"
        type="button"
        aria-label="Notă explicativă"
        aria-expanded={open}
        title="Notă explicativă"
        onClick={() => setOpen((current) => !current)}
      >
        ?
      </button>
      {open ? <span className="piece-note-bubble" role="tooltip">{cleanNote}</span> : null}
    </span>
  );
}
export function fallbackPiece(kind) {
  const pool = kind === "poem" ? POEMS : STORIES;
  const item = pool[0];
  return {
    ...item,
    categoryLabel: kind === "poem" ? "Poezie" : "Proză scurtă"
  };
}
export function RevealText({ text, keySeed }) {
  const lines = useMemo(() => text.split("\n"), [text]);
  return (
    <div className="reveal-text" key={keySeed}>
      {lines.map((line, index) => {
        if (line.trim() === "") {
          return (
            <div key={index} className="reveal-line reveal-blank">
              &nbsp;
            </div>
          );
        }

        return (
          <div key={index} className="reveal-line" style={{ animationDelay: `${0.08 + index * 0.035}s` }}>
            {line}
          </div>
        );
      })}
    </div>
  );
}

const TEXT_DOUBLE_TAP_MAX_MS = 420;
const TEXT_DOUBLE_TAP_MAX_DISTANCE = 28;
const TEXT_TAP_MOVE_TOLERANCE = 10;
const TEXT_HINT_DISMISSED_STORAGE_KEY = "calimara.reader.textGestureHintDismissed";

function pointerDistance(first, second) {
  if (!first || !second) return Number.POSITIVE_INFINITY;
  return Math.hypot(first.x - second.x, first.y - second.y);
}

function isInteractiveGestureTarget(target, root) {
  if (typeof Element === "undefined" || !(target instanceof Element)) return false;
  const interactive = target.closest("a, button, input, textarea, select, summary, [role='button'], [contenteditable='true']");
  return Boolean(interactive && root.contains(interactive));
}

function hasDismissedTextHint() {
  try {
    return typeof window !== "undefined" && window.sessionStorage.getItem(TEXT_HINT_DISMISSED_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

function markTextHintDismissed() {
  try {
    window.sessionStorage.setItem(TEXT_HINT_DISMISSED_STORAGE_KEY, "1");
  } catch {
    // Session storage can be unavailable in restricted browser modes.
  }
}

export function ModerationOverlay({ children = TEXT_MODERATION_MESSAGE, className = "" }) {
  return (
    <div className={`piece-moderation-overlay ${className}`.trim()} role="status" aria-live="polite">
      <p>{children}</p>
    </div>
  );
}

export function PieceCol({ piece, animKey, titleAction = null, titlePrefix = null, readerFooter = null, moderationOverlayText = "", onTextDoubleActivate = null, showTextGestureHint = true }) {
  const scrollRef = useRef(null);
  const bodyRef = useRef(null);
  const tapRef = useRef({ down: null, lastTap: null });
  const textActivationRef = useRef(0);
  const [textHintDismissed, setTextHintDismissed] = useState(hasDismissedTextHint);
  const [textHintDismissing, setTextHintDismissing] = useState(false);
  const [scrollState, setScrollState] = useState({
    atTop: true,
    atBottom: true,
    hasOverflow: false,
    readPercent: 100
  });
  const syncScrollState = useCallback((node = scrollRef.current) => {
    const el = node;
    if (!el) return;
    const scrollHeight = Math.max(1, el.scrollHeight);
    const clientHeight = Math.max(1, el.clientHeight);
    const hasOverflow = scrollHeight > clientHeight + 1;
    const atTop = el.scrollTop < 4;
    const atBottom = !hasOverflow || el.scrollTop + clientHeight >= scrollHeight - 4;
    const readPercent = hasOverflow
      ? Math.max(0, Math.min(100, Math.round(((el.scrollTop + clientHeight) / scrollHeight) * 100)))
      : 100;

    setScrollState((prev) => {
      if (
        prev.atTop === atTop &&
        prev.atBottom === atBottom &&
        prev.hasOverflow === hasOverflow &&
        prev.readPercent === readPercent
      ) {
        return prev;
      }
      return { atTop, atBottom, hasOverflow, readPercent };
    });
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return undefined;
    el.scrollTop = 0;
    syncScrollState(el);
    const frame = window.requestAnimationFrame(() => syncScrollState(el));
    return () => window.cancelAnimationFrame(frame);
  }, [animKey, syncScrollState]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return undefined;
    const sync = () => syncScrollState(el);
    window.addEventListener("resize", sync);
    let observer = null;
    if (typeof ResizeObserver !== "undefined") {
      observer = new ResizeObserver(sync);
      observer.observe(el);
      if (bodyRef.current) observer.observe(bodyRef.current);
    }
    sync();
    return () => {
      window.removeEventListener("resize", sync);
      if (observer) observer.disconnect();
    };
  }, [syncScrollState]);

  const onScroll = (event) => {
    syncScrollState(event.currentTarget);
  };

  const activateTextGesture = useCallback(() => {
    if (!onTextDoubleActivate) return;
    const now = Date.now();
    if (now - textActivationRef.current < TEXT_DOUBLE_TAP_MAX_MS) return;
    textActivationRef.current = now;
    onTextDoubleActivate();
  }, [onTextDoubleActivate]);

  const triggerTextDoubleActivate = useCallback((event) => {
    if (!onTextDoubleActivate) return;
    if (isInteractiveGestureTarget(event.target, event.currentTarget)) return;
    event.preventDefault();
    activateTextGesture();
  }, [activateTextGesture, onTextDoubleActivate]);

  const onTextPointerDown = (event) => {
    if (!onTextDoubleActivate) return;
    if (event.pointerType === "mouse" || event.button !== 0 || event.isPrimary === false) return;
    if (isInteractiveGestureTarget(event.target, event.currentTarget)) return;
    tapRef.current.down = {
      id: event.pointerId,
      x: event.clientX,
      y: event.clientY,
      time: Date.now()
    };
  };

  const onTextPointerUp = (event) => {
    if (!onTextDoubleActivate) return;
    if (event.pointerType === "mouse" || event.isPrimary === false) return;
    if (isInteractiveGestureTarget(event.target, event.currentTarget)) return;

    const down = tapRef.current.down;
    tapRef.current.down = null;
    if (!down || down.id !== event.pointerId) return;

    const currentTap = { x: event.clientX, y: event.clientY, time: Date.now() };
    if (currentTap.time - down.time > TEXT_DOUBLE_TAP_MAX_MS) return;
    if (pointerDistance(down, currentTap) > TEXT_TAP_MOVE_TOLERANCE) return;

    const previousTap = tapRef.current.lastTap;
    if (
      previousTap &&
      currentTap.time - previousTap.time <= TEXT_DOUBLE_TAP_MAX_MS &&
      pointerDistance(previousTap, currentTap) <= TEXT_DOUBLE_TAP_MAX_DISTANCE
    ) {
      event.preventDefault();
      tapRef.current.lastTap = null;
      activateTextGesture();
      return;
    }

    tapRef.current.lastTap = currentTap;
  };

  const onTextPointerCancel = () => {
    tapRef.current.down = null;
  };

  const dismissTextHint = () => {
    markTextHintDismissed();
    setTextHintDismissing(true);
  };

  const titleContent = piece.postUrl && piece.postUrl !== "#" ? (
    <a href={piece.postUrl}>{piece.title}</a>
  ) : piece.title;
  const hasTitleActions = Boolean(titleAction || piece.explanatoryNote);
  const titleNode = (
    <h1 className="piece-title">
      {titleContent}
      {hasTitleActions ? (
        <span className="piece-title-actions">
          {titleAction ? <span className="piece-title-action">{titleAction}</span> : null}
          {piece.explanatoryNote ? <ExplanatoryNoteBubble note={piece.explanatoryNote} /> : null}
        </span>
      ) : null}
    </h1>
  );
  const titleHeading = titlePrefix ? (
    <div className="piece-title-row">
      <span className="piece-title-prefix">{titlePrefix}</span>
      {titleNode}
    </div>
  ) : titleNode;
  const showAuthorTextHint = onTextDoubleActivate && showTextGestureHint && !textHintDismissed;

  return (
    <div className="piece-col">
      {titleHeading}
      <div className="piece-meta">
        {piece.authorUrl ? (
          <AuthorLink user={piece.authorUser} username={piece.author} className="piece-author">{authorDomainHandle(piece.author)}</AuthorLink>
        ) : (
          <span className="piece-author">{piece.author}</span>
        )}
        {piece.year ? (
          <>
            <span className="piece-meta-dot" />
            <span className="piece-year">{piece.year}</span>
          </>
        ) : null}
      </div>
      <div className="piece-scroll-wrap">
        <div ref={scrollRef} className={`piece-scroll ${scrollState.atTop ? "at-top" : ""} ${scrollState.atBottom ? "at-bottom" : ""}`} onScroll={onScroll}>
          <div ref={bodyRef} className="piece-body-inner">
            {showAuthorTextHint ? (
              <div
                className={`piece-text-hint ${textHintDismissing ? "is-dismissing" : ""}`.trim()}
                onTransitionEnd={(event) => {
                  if (event.currentTarget !== event.target) return;
                  if (event.propertyName !== "max-height") return;
                  if (textHintDismissing) setTextHintDismissed(true);
                }}
              >
                <span className="piece-next-hint">
                  <span className="piece-next-hint-copy">Dublu click sau dublu tap ca să treci la postarea următoare.</span>
                  <button
                    className="piece-next-hint-dismiss"
                    type="button"
                    aria-label="Ascunde indiciul de dublu click"
                    title="Ascunde"
                    onClick={dismissTextHint}
                  >
                    x
                  </button>
                </span>
              </div>
            ) : null}
            <div
              className={`piece-text-gesture-zone ${onTextDoubleActivate ? "can-double-activate" : ""}`.trim()}
              data-reader-text-zone={onTextDoubleActivate ? "landing-shuffle" : undefined}
              onDoubleClick={triggerTextDoubleActivate}
              onPointerDown={onTextPointerDown}
              onPointerUp={onTextPointerUp}
              onPointerCancel={onTextPointerCancel}
              onPointerLeave={onTextPointerCancel}
            >
              {hasHtml(piece.contentHtml) ? (
                <RichTextContent html={piece.contentHtml} className="piece-rich-text" />
              ) : (
                <RevealText text={piece.body || ""} keySeed={animKey} />
              )}
              <div className="piece-end">
                <span>fin</span>
                <span className="piece-end-mark">· · ·</span>
              </div>
            </div>
            {readerFooter ? <div className="piece-reader-footer">{readerFooter}</div> : null}
          </div>
        </div>
        {moderationOverlayText ? <ModerationOverlay>{moderationOverlayText}</ModerationOverlay> : null}
        <div className={`scroll-hint-wrap ${scrollState.hasOverflow ? "" : "hidden"}`} aria-hidden="true">
          <div className="scroll-hint">
            <span className="scroll-hint-label">
              <svg width="12" height="12" viewBox="0 0 14 14" fill="none">
                <path d="M3 5l4 4 4-4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <span>derulează</span>
              <span className="scroll-progress">({scrollState.readPercent}%)</span>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
export function PostCard({ post }) {
  if (post.moderation_status === "rejected") return null;
  const href = postHref(post);
  const excerpt = htmlToText(post.content);
  const moderationText = moderationLabel(post.moderation_status);
  const moderationClass = post.moderation_status ? `status-${post.moderation_status}` : "";
  const moderationTitle = post.moderation_reason
    ? `${moderationText}: ${post.moderation_reason}`
    : moderationText;
  const moderationOverlayText = MODERATING_STATUSES.has(post.moderation_status)
    ? TEXT_MODERATION_MESSAGE
    : "";
  return (
    <article className={`piece-card ${post.super_likes_count > 0 ? "has-super-like" : ""}`}>
      <div className="piece-card-kicker-row">
        <span className="piece-card-kicker">{post.category_name ?? categoryLabel(post.category)}</span>
        {moderationText && !moderationOverlayText ? (
          <span className={`piece-card-status ${moderationClass}`} title={moderationTitle}>
            {moderationText}
          </span>
        ) : null}
      </div>
      <h2 className="piece-card-title">
        <PostTitleLink post={post}>{post.title}</PostTitleLink>
      </h2>
      <div className={`piece-card-excerpt-wrap ${moderationOverlayText ? "has-moderation-overlay" : ""}`.trim()}>
        {href && href !== "#" ? (
          <a className="piece-card-excerpt piece-card-excerpt-link" href={href}>{excerpt}</a>
        ) : (
          <p className="piece-card-excerpt">{excerpt}</p>
        )}
        {moderationOverlayText ? <ModerationOverlay className="piece-card-moderation-overlay" /> : null}
      </div>
      <div className="piece-card-meta">
        {post.owner?.username ? <AuthorLink user={post.owner} /> : null}
        {post.created_at ? <span>{formatDateTime(post.created_at)}</span> : null}
      </div>
    </article>
  );
}
export function EquippedStrip({ items }) {
  if (!items?.length) return null;
  return (
    <div className="cosmetic-strip" aria-label="Cosmetice echipate">
      {items.map((entry) => (
        <span className="cosmetic-chip" key={`${entry.slot}-${entry.item?.id}`}>
          <span>{slotLabel(entry.slot)}</span>
          <strong>{entry.item?.name}</strong>
        </span>
      ))}
    </div>
  );
}
