import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { POEMS, STORIES } from "../content.js";
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
export function CompactAudioPlayer({
  src,
  downloadUrl,
  className = "",
  showDownload = true,
  downloadLabel = "Descarcă",
  disabledTitle = ""
}) {
  const audioRef = useRef(null);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState("");
  const disabled = !src;

  useEffect(() => {
    const audio = audioRef.current;
    setPlaying(false);
    setCurrentTime(0);
    setDuration(0);
    setError("");
    if (audio) {
      audio.pause();
      audio.currentTime = 0;
      if (src) audio.load();
    }
  }, [src]);

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
        onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime)}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => {
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
      <button className="compact-audio-play" type="button" onClick={togglePlayback} disabled={disabled} aria-label={playing ? "Pauză audio" : "Redă audio"}>
        {playing ? "Pauză" : "Redă"}
      </button>
      <span className="compact-audio-time" aria-label="Timp audio">
        {formatAudioTime(currentTime)} / {formatAudioTime(duration)}
      </span>
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
    sourceUrl: authorUrl,
    explanatoryNote: post.explanatory_note || ""
  };
}
export function postHref(post) {
  return post?.owner ? `${blogUrl(post.owner.username)}/${post.slug}` : post?.url || "#";
}
function sourceUrlLabel(sourceUrl) {
  const rawUrl = String(sourceUrl || "").trim();
  if (!rawUrl || rawUrl === "#") return "";

  try {
    const baseUrl = typeof window !== "undefined" ? window.location.href : undefined;
    return new URL(rawUrl, baseUrl).host || rawUrl;
  } catch {
    return rawUrl.replace(/^https?:\/\//i, "").replace(/\/$/, "");
  }
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
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        Notă explicativă
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
    categoryLabel: kind === "poem" ? "Poezie" : "Proză scurtă",
    sourceUrl: "#"
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
export function PieceCol({ piece, animKey, titleAction = null, titlePrefix = null, readerFooter = null }) {
  const scrollRef = useRef(null);
  const bodyRef = useRef(null);
  const [scrollState, setScrollState] = useState({
    atTop: true,
    atBottom: true,
    hasOverflow: false,
    readPercent: 100
  });
  const sourceLabel = sourceUrlLabel(piece.sourceUrl);

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

  const titleContent = piece.postUrl && piece.postUrl !== "#" ? (
    <a href={piece.postUrl}>{piece.title}</a>
  ) : piece.title;
  const titleNode = (
    <h1 className="piece-title">
      {titleContent}
      {titleAction ? <span className="piece-title-action">{titleAction}</span> : null}
    </h1>
  );
  const titleHeading = titlePrefix ? (
    <div className="piece-title-row">
      <span className="piece-title-prefix">{titlePrefix}</span>
      {titleNode}
    </div>
  ) : titleNode;

  return (
    <div className="piece-col">
      {sourceLabel ? (
        <div className="piece-kind-row">
          <a className="piece-kind-meta" href={piece.sourceUrl}>
            {sourceLabel}
          </a>
        </div>
      ) : null}
      {titleHeading}
      <div className="piece-meta">
        {piece.authorUrl ? (
          <AuthorLink user={piece.authorUser} username={piece.author} className="piece-author">{piece.author}</AuthorLink>
        ) : (
          <span className="piece-author">{piece.author}</span>
        )}
        {piece.year ? (
          <>
            <span className="piece-meta-dot" />
            <span className="piece-year">{piece.year}</span>
          </>
        ) : null}
        {piece.explanatoryNote ? (
          <>
            <span className="piece-meta-dot" />
            <ExplanatoryNoteBubble note={piece.explanatoryNote} />
          </>
        ) : null}
      </div>
      <div className="piece-scroll-wrap">
        <div ref={scrollRef} className={`piece-scroll ${scrollState.atTop ? "at-top" : ""} ${scrollState.atBottom ? "at-bottom" : ""}`} onScroll={onScroll}>
          <div ref={bodyRef} className="piece-body-inner">
            {hasHtml(piece.contentHtml) ? (
              <RichTextContent html={piece.contentHtml} className="piece-rich-text" />
            ) : (
              <RevealText text={piece.body || ""} keySeed={animKey} />
            )}
            <div className="piece-end">
              <span>fin</span>
              <span className="piece-end-mark">· · ·</span>
            </div>
            {readerFooter ? <div className="piece-reader-footer">{readerFooter}</div> : null}
          </div>
        </div>
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
  const moderationText = moderationLabel(post.moderation_status);
  const moderationClass = post.moderation_status ? `status-${post.moderation_status}` : "";
  const moderationTitle = post.moderation_reason
    ? `${moderationText}: ${post.moderation_reason}`
    : moderationText;
  return (
    <article className={`piece-card ${post.super_likes_count > 0 ? "has-super-like" : ""}`}>
      <div className="piece-card-kicker-row">
        <span className="piece-card-kicker">{post.category_name ?? categoryLabel(post.category)}</span>
        {moderationText ? (
          <span className={`piece-card-status ${moderationClass}`} title={moderationTitle}>
            {moderationText}
          </span>
        ) : null}
      </div>
      <h2 className="piece-card-title">
        <PostTitleLink post={post}>{post.title}</PostTitleLink>
      </h2>
      <p className="piece-card-excerpt">{htmlToText(post.content)}</p>
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
