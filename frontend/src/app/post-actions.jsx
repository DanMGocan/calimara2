import { useCallback, useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { FaFlag, FaHandsHelping, FaHeart, FaRegLaughSquint } from "react-icons/fa";
import { FiCheck, FiChevronDown, FiDownload, FiEye, FiList, FiMessageCircle, FiPlus } from "react-icons/fi";
import { TfiThought } from "react-icons/tfi";
import { addPostToAudioPlaylist, createAudioPlaylist, fetchAudioPlaylists, fetchPostAudioStatus } from "../api/audio.js";
import { createComment, likePost, reactToComment, removeCommentReaction, reportPost } from "../api/posts.js";
import { addSuperLike } from "../api/super-likes.js";
import { promoteAuthor, promotePost, searchUsers } from "../api/users.js";
import { addDiacritics } from "../api/writing.js";
import { useAuthModal } from "./auth-modal.jsx";
import { COMMENT_CHARACTER_LIMIT, MODERATING_STATUSES, TEXT_MODERATION_MESSAGE } from "./constants.js";
import { CompactAudioPlayer, ModerationOverlay, RichTextContent } from "./content.jsx";
import { DiacriticsControl, DiacriticsProgressOverlay, DiacriticsReviewPanel, diacriticsSubmitLabel, useDiacriticsProgress, useDiacriticsQuota } from "./diacritics.jsx";
import { RichTextEditor } from "./editor.jsx";
import { formatDateTime, formatNumber, htmlToText, usernameHandle } from "./format.js";
import { mainPath } from "./paths.js";

const NO_AUDIO_TITLE = "Utilizatorul nu a convertit încă textul în fișier audio";
const REPORT_TITLES = {
  offensive: "Raportează conținut ofensiv",
  plagiarism: "Raportează plagiat"
};
const COMMENT_REACTIONS = [
  { type: "helpful", label: "Util", Icon: FaHandsHelping },
  { type: "funny", label: "Amuzant", Icon: FaRegLaughSquint },
  { type: "insightful", label: "Profund", Icon: TfiThought }
];

function AccessModal({ modal, onClose }) {
  if (!modal) return null;
  return (
    <div className="access-modal-scrim" role="presentation" onClick={onClose}>
      <section className="access-modal" role="dialog" aria-modal="true" aria-labelledby="access-modal-title" onClick={(event) => event.stopPropagation()}>
        <button className="access-modal-close" type="button" aria-label="Închide" onClick={onClose}>x</button>
        <div className="piece-card-kicker">{modal.kicker || "călimara.ro"}</div>
        <h2 id="access-modal-title" className="access-modal-title">{modal.title}</h2>
        <p className="access-modal-body">{modal.message}</p>
        <div className="button-row">
          {modal.actionHref ? <a className="cal-btn primary" href={modal.actionHref}>{modal.actionLabel}</a> : null}
          <button className="cal-btn" type="button" onClick={onClose}>Închide</button>
        </div>
      </section>
    </div>
  );
}

export function ReportModal({
  modal,
  busy,
  details,
  evidenceUrl,
  allowPlagiarism = true,
  onDetailsChange,
  onEvidenceUrlChange,
  onSelectReason,
  onClose,
  onSubmit
}) {
  if (!modal) return null;
  const isPlagiarism = modal.reasonType === "plagiarism";
  const choosingReason = !modal.reasonType;
  return (
    <div className="access-modal-scrim" role="presentation" onClick={onClose}>
      <section className="access-modal" role="dialog" aria-modal="true" aria-labelledby="report-modal-title" onClick={(event) => event.stopPropagation()}>
        <button className="access-modal-close" type="button" aria-label="Închide" onClick={onClose}>x</button>
        <div className="piece-card-kicker">raportare</div>
        <h2 id="report-modal-title" className="access-modal-title">
          {choosingReason ? "Raportează" : REPORT_TITLES[modal.reasonType]}
        </h2>
        {choosingReason ? (
          <div className="report-choice-list">
            <button className="report-choice-btn" type="button" onClick={() => onSelectReason("offensive")}>
              Raportează conținut ofensiv
            </button>
            {allowPlagiarism ? (
              <button className="report-choice-btn" type="button" onClick={() => onSelectReason("plagiarism")}>
                Raportează plagiat
              </button>
            ) : null}
          </div>
        ) : (
          <form className="report-form" onSubmit={onSubmit}>
            {isPlagiarism ? (
              <label className="auth-field">
                Link sursă
                <input className="cal-input" type="url" value={evidenceUrl} onChange={(event) => onEvidenceUrlChange(event.target.value)} placeholder="https://..." maxLength={1000} />
              </label>
            ) : null}
            <label className="auth-field">
              Detalii
              <textarea className="cal-input" value={details} onChange={(event) => onDetailsChange(event.target.value)} rows={4} maxLength={2000} />
            </label>
            <div className="button-row">
              <button className="cal-btn primary" type="submit" disabled={busy === "report"}>
                {busy === "report" ? "Se trimite..." : "Trimite raportarea"}
              </button>
              <button className="cal-btn" type="button" onClick={onClose}>Închide</button>
            </div>
          </form>
        )}
      </section>
    </div>
  );
}

function PlaylistModal({
  open,
  loading,
  playlists,
  addedIds,
  status,
  busy,
  title,
  onTitleChange,
  onClose,
  onReload,
  onAdd,
  onCreate
}) {
  if (!open) return null;
  const cleanTitle = title.trim();
  return (
    <div className="access-modal-scrim" role="presentation" onClick={onClose}>
      <section className="access-modal playlist-modal" role="dialog" aria-modal="true" aria-labelledby="playlist-modal-title" onClick={(event) => event.stopPropagation()}>
        <button className="access-modal-close" type="button" aria-label="Închide" onClick={onClose}>x</button>
        <div className="piece-card-kicker">playlisturi</div>
        <h2 id="playlist-modal-title" className="access-modal-title">Adaugă în playlist</h2>
        <div className="playlist-modal-create">
          <input
            className="cal-input"
            value={title}
            onChange={(event) => onTitleChange(event.target.value)}
            maxLength={120}
            placeholder="Playlist nou"
            aria-label="Titlu playlist nou"
          />
          <button className="cal-btn primary" type="button" onClick={onCreate} disabled={Boolean(busy) || !cleanTitle}>
            <FiPlus aria-hidden="true" />
            Creează
          </button>
        </div>
        {loading ? <p className="auth-sub">Se încarcă playlisturile...</p> : null}
        {status ? <p className="inline-error">{status}</p> : null}
        {!loading && playlists.length ? (
          <div className="playlist-modal-list">
            {playlists.map((playlist) => {
              const added = addedIds.has(playlist.id);
              return (
                <button
                  className={`playlist-modal-item ${added ? "is-added" : ""}`.trim()}
                  type="button"
                  key={playlist.id}
                  onClick={() => onAdd(playlist)}
                  disabled={Boolean(busy) || added}
                  aria-pressed={added}
                >
                  {added ? <FiCheck aria-hidden="true" /> : <FiList aria-hidden="true" />}
                  <span>{playlist.title}</span>
                  <small>{added ? "adăugat" : `${formatNumber(playlist.item_count || 0)} texte`}</small>
                </button>
              );
            })}
          </div>
        ) : null}
        {!loading && !playlists.length ? <p className="auth-sub">Nu ai playlisturi încă.</p> : null}
        <div className="button-row">
          <button className="cal-btn" type="button" onClick={onReload} disabled={loading || Boolean(busy)}>Reîncarcă</button>
          <button className="cal-btn" type="button" onClick={onClose}>Închide</button>
        </div>
      </section>
    </div>
  );
}

function MetricCount({ value }) {
  const text = String(value ?? "");
  return (
    <span className="react-count metric-count" key={text}>
      {text}
    </span>
  );
}

function CommentReactionRow({ comment, user, busy, onReact }) {
  const counts = comment.reaction_counts || {};
  const commentBusy = String(busy || "").startsWith(`comment-reaction:${comment.id}:`);
  const ownComment = Boolean(user?.id && comment.user_id === user.id);
  return (
    <div className="comment-reactions" aria-label="Reacții comentariu">
      {COMMENT_REACTIONS.map(({ type, label, Icon }) => {
        const active = comment.viewer_reaction === type;
        const count = formatNumber(Number(counts[type] || 0));
        const title = ownComment ? "Nu poți reacționa la propriul comentariu" : label;
        return (
          <button
            className={`comment-reaction-btn comment-reaction-${type} ${active ? "on" : ""}`}
            type="button"
            key={type}
            onClick={() => onReact(comment, type)}
            disabled={commentBusy || ownComment}
            aria-pressed={active}
            aria-label={`${label}: ${count}${ownComment ? ". Nu poți reacționa la propriul comentariu." : ""}`}
            title={title}
          >
            <Icon className="comment-reaction-symbol" aria-hidden="true" focusable="false" />
            <MetricCount value={count} />
          </button>
        );
      })}
    </div>
  );
}

function pdfFilename(post) {
  const stem = String(post?.slug || "calimara-export").replace(/\.pdf$/i, "").trim();
  return `${stem || "calimara-export"}.pdf`;
}

export function PostPromotionMenu({ post, author, user }) {
  const buttonRef = useRef(null);
  const modalTitleId = useId();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");

  useEffect(() => {
    setOpen(false);
    setBusy("");
    setStatus("");
  }, [post?.id, author?.id, user?.id]);

  useEffect(() => {
    if (!open || typeof document === "undefined") return undefined;

    const previousOverflow = document.body.style.overflow;
    const onKeyDown = (event) => {
      if (event.key === "Escape") setOpen(false);
    };

    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const promoteCurrentPost = async () => {
    if (!user) return;
    if (!post?.id || busy) return;
    setBusy("post");
    setStatus("");
    try {
      await promotePost(post.id);
      setStatus("Postarea este promovată pe profilul tău.");
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut promova postarea.");
    } finally {
      setBusy("");
    }
  };

  const promoteCurrentAuthor = async () => {
    if (!user) return;
    if (!author?.id || busy) return;
    if (author.id === user.id) {
      setStatus("Nu te poți promova pe tine ca autor extern.");
      return;
    }
    setBusy("author");
    setStatus("");
    try {
      await promoteAuthor(author.id);
      setStatus("Autorul este promovat pe profilul tău.");
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut promova autorul.");
    } finally {
      setBusy("");
    }
  };

  const promotionModal = open && typeof document !== "undefined" ? createPortal(
    <div className="access-modal-scrim title-promotion-scrim" role="presentation" onClick={() => setOpen(false)}>
      <section
        className="access-modal title-promotion-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={modalTitleId}
        onClick={(event) => event.stopPropagation()}
      >
        <button className="access-modal-close" type="button" aria-label="Închide" onClick={() => setOpen(false)}>x</button>
        <div className="piece-card-kicker">promovare</div>
        <h2 id={modalTitleId} className="access-modal-title">Opțiuni de promovare</h2>
        <div className="title-promotion-modal-options">
          <button className="title-promotion-option" type="button" onClick={promoteCurrentPost} disabled={!user || Boolean(busy)}>
            {busy === "post" ? "Se promovează..." : "Promovează postarea pe profilul tău"}
          </button>
          <button className="title-promotion-option" type="button" onClick={promoteCurrentAuthor} disabled={!user || Boolean(busy)}>
            {busy === "author" ? "Se promovează..." : "Promovează autorul pe profilul tău"}
          </button>
        </div>
        {status ? <p className="title-promotion-status title-promotion-modal-status" role="status">{status}</p> : null}
      </section>
    </div>,
    document.body
  ) : null;

  return (
    <span className="title-promotion-menu">
      <button
        className={`title-promotion-toggle ${open ? "open" : ""}`.trim()}
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((current) => !current)}
        aria-label="Opțiuni de promovare"
        aria-expanded={open}
        title="Opțiuni de promovare"
      >
        <FiChevronDown aria-hidden="true" />
      </button>
      {promotionModal}
    </span>
  );
}

function CommentPanel({
  post,
  user,
  busy,
  commentText,
  commentAutoDiacritics,
  commentReview,
  diacriticsQuota,
  diacriticsQuotaLoading,
  diacriticsQuotaError,
  onCommentTextChange,
  onCommentAutoDiacriticsChange,
  onCommentReviewChange,
  onLoginRequired,
  onReactToComment,
  onSubmit,
  submitButtonRef
}) {
  const comments = Array.isArray(post.approved_comments) ? post.approved_comments : [];
  const editorId = `post-comment-${post.id}`;

  return (
    <div className="piece-comments" id={`comments-${post.id}`}>
      {comments.length ? (
        <ul className="comment-list">
          {comments.filter((comment) => comment.moderation_status !== "rejected").map((comment) => {
            const author = comment.user?.username ? usernameHandle(comment.user.username) : comment.author_name || "cititor";
            const isModerating = MODERATING_STATUSES.has(comment.moderation_status);
            return (
              <li className={`comment ${isModerating ? "has-moderation-overlay" : ""}`.trim()} id={`comment-${comment.id}`} key={comment.id}>
                <div className="comment-head">
                  <span className="comment-author">{author}</span>
                  {comment.created_at ? <span className="comment-time">{formatDateTime(comment.created_at)}</span> : null}
                </div>
                <div className={`comment-body-wrap ${isModerating ? "has-moderation-overlay" : ""}`.trim()}>
                  <RichTextContent html={comment.content} className="comment-body" />
                  {isModerating ? (
                    <ModerationOverlay className="comment-moderation-overlay">{TEXT_MODERATION_MESSAGE}</ModerationOverlay>
                  ) : null}
                </div>
                {!isModerating ? (
                  <CommentReactionRow comment={comment} user={user} busy={busy} onReact={onReactToComment} />
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="auth-sub post-comments-empty">Nu există comentarii încă.</p>
      )}

      {user ? (
        <form className="landing-comment-panel post-comment-form" onSubmit={onSubmit}>
          <label className="auth-field" htmlFor={editorId}>Comentariu</label>
          <RichTextEditor id={editorId} className="compact" value={commentText} onChange={onCommentTextChange} maxLength={COMMENT_CHARACTER_LIMIT} mentionSearch={searchUsers} />
          <DiacriticsControl
            user={user}
            enabled={commentAutoDiacritics}
            disabled={Boolean(commentReview)}
            quota={diacriticsQuota}
            quotaLoading={diacriticsQuotaLoading}
            quotaError={diacriticsQuotaError}
            onChange={(checked) => {
              onCommentAutoDiacriticsChange(checked);
              onCommentReviewChange(null);
            }}
          />
          <DiacriticsReviewPanel
            active={Boolean(commentReview)}
            changed={Boolean(commentReview?.changed)}
            onReset={commentReview ? () => {
              onCommentTextChange(commentReview.originalContent);
              onCommentReviewChange(null);
            } : null}
          />
          <div className="post-comment-actions">
            <button ref={submitButtonRef} className="cal-btn primary post-comment-submit" type="submit" disabled={busy === "comment"}>
              {diacriticsSubmitLabel({
                submitting: busy === "comment",
                reviewing: Boolean(commentReview),
                enabled: Boolean(user && commentAutoDiacritics),
                submitLabel: "Trimite comentariul"
              })}
            </button>
            {user && commentAutoDiacritics && !commentReview ? (
              <button className="cal-btn post-comment-submit" type="button" onClick={() => submitComment(null, { skipDiacritics: true })} disabled={busy === "comment"}>
                Trimite fără Diacritice
              </button>
            ) : null}
          </div>
        </form>
      ) : (
        <div className="post-comment-auth">
          <button className="cal-btn primary" type="button" onClick={onLoginRequired}>Autentifică-te ca să comentezi</button>
        </div>
      )}
    </div>
  );
}

export function PostActionTools({ post, user, onPostChange, pdfHref = "#", className = "" }) {
  const { openAuthModal } = useAuthModal();
  const [postState, setPostState] = useState(post);
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");
  const [modal, setModal] = useState(null);
  const [reportModal, setReportModal] = useState(null);
  const [reportDetails, setReportDetails] = useState("");
  const [reportEvidenceUrl, setReportEvidenceUrl] = useState("");
  const [playlistModalOpen, setPlaylistModalOpen] = useState(false);
  const [playlistOptions, setPlaylistOptions] = useState([]);
  const [playlistAddedIds, setPlaylistAddedIds] = useState(() => new Set());
  const [playlistLoading, setPlaylistLoading] = useState(false);
  const [playlistStatus, setPlaylistStatus] = useState("");
  const [newPlaylistTitle, setNewPlaylistTitle] = useState("");
  const [audioState, setAudioState] = useState({ loading: false, data: null, error: "" });
  const [commentOpen, setCommentOpen] = useState(false);
  const [commentText, setCommentText] = useState("");
  const [commentAutoDiacritics, setCommentAutoDiacritics] = useState(false);
  const [commentReview, setCommentReview] = useState(null);
  const commentSubmitRef = useRef(null);
  const {
    diacriticsProgress,
    startDiacriticsProgress,
    finishDiacriticsProgress,
    failDiacriticsProgress
  } = useDiacriticsProgress();
  const {
    diacriticsQuota,
    diacriticsQuotaLoading,
    diacriticsQuotaError,
    applyDiacriticsQuota
  } = useDiacriticsQuota(user);

  useEffect(() => {
    setPostState(post);
    setStatus("");
    setModal(null);
    setReportModal(null);
    setReportDetails("");
    setReportEvidenceUrl("");
    setPlaylistModalOpen(false);
    setPlaylistOptions([]);
    setPlaylistAddedIds(new Set());
    setPlaylistStatus("");
    setNewPlaylistTitle("");
    setCommentOpen(false);
    setCommentText("");
    setCommentReview(null);
  }, [post?.id, user?.id]);

  useEffect(() => {
    setCommentAutoDiacritics(false);
    setCommentReview(null);
  }, [user?.id]);

  useEffect(() => {
    if (!commentOpen || !commentReview) return undefined;
    const frame = window.requestAnimationFrame(() => {
      commentSubmitRef.current?.scrollIntoView({ block: "nearest" });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [commentOpen, commentReview]);

  useEffect(() => {
    if (!post?.id) return undefined;
    let cancelled = false;
    setAudioState({ loading: true, data: null, error: "" });
    fetchPostAudioStatus(post.id)
      .then((data) => {
        if (!cancelled) setAudioState({ loading: false, data, error: "" });
      })
      .catch((requestError) => {
        if (!cancelled) {
          setAudioState({
            loading: false,
            data: null,
            error: requestError.message || "Nu am putut încărca audio."
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [post?.id]);

  const loadPlaylistOptions = useCallback(async () => {
    if (!postState?.id || !user?.has_author_audio_access) return;
    setPlaylistLoading(true);
    setPlaylistStatus("");
    try {
      const [allData, addedData] = await Promise.all([
        fetchAudioPlaylists(),
        fetchAudioPlaylists(postState.id)
      ]);
      setPlaylistOptions(Array.isArray(allData?.playlists) ? allData.playlists : []);
      setPlaylistAddedIds(new Set((addedData?.playlists || []).map((playlist) => playlist.id)));
    } catch (requestError) {
      setPlaylistStatus(requestError.message || "Nu am putut încărca playlisturile.");
    } finally {
      setPlaylistLoading(false);
    }
  }, [postState?.id, user?.has_author_audio_access]);

  const openPlaylistModal = () => {
    if (!user) {
      showLoginModal("Pentru playlisturi trebuie să intri în cont.");
      return;
    }
    if (!user.has_author_audio_access) {
      setModal({
        kicker: "playlisturi",
        title: "Playlisturi indisponibile",
        message: "Crearea playlisturilor necesită abonament Rapsod.",
        actionHref: mainPath("/premium"),
        actionLabel: "Vezi Premium"
      });
      return;
    }
    setPlaylistModalOpen(true);
    setPlaylistStatus("");
    setNewPlaylistTitle("");
    loadPlaylistOptions();
  };

  const addCurrentPostToPlaylist = async (playlist) => {
    if (!playlist?.id || !postState?.id || playlistAddedIds.has(playlist.id)) return;
    setBusy(`playlist:${playlist.id}`);
    setPlaylistStatus("");
    try {
      await addPostToAudioPlaylist(playlist.id, postState.id);
      setPlaylistAddedIds((current) => new Set([...current, playlist.id]));
      setPlaylistOptions((current) => current.map((item) => (
        item.id === playlist.id ? { ...item, item_count: Number(item.item_count || 0) + 1 } : item
      )));
      setPlaylistStatus("Postarea a fost adăugată în playlist.");
    } catch (requestError) {
      setPlaylistStatus(requestError.message || "Nu am putut adăuga postarea în playlist.");
    } finally {
      setBusy("");
    }
  };

  const createPlaylistAndAddPost = async () => {
    const title = newPlaylistTitle.trim();
    if (!title || !postState?.id) return;
    setBusy("playlist:create");
    setPlaylistStatus("");
    try {
      const playlist = await createAudioPlaylist(title);
      await addPostToAudioPlaylist(playlist.id, postState.id);
      setPlaylistOptions((current) => [{ ...playlist, item_count: 1 }, ...current]);
      setPlaylistAddedIds((current) => new Set([...current, playlist.id]));
      setNewPlaylistTitle("");
      setPlaylistStatus("Playlistul a fost creat și postarea a fost adăugată.");
    } catch (requestError) {
      setPlaylistStatus(requestError.message || "Nu am putut crea playlistul.");
    } finally {
      setBusy("");
    }
  };

  if (!postState) return null;

  const comments = Array.isArray(postState.approved_comments) ? postState.approved_comments : [];
  const commentsCount = Number(postState.comments_count ?? comments.length ?? 0);
  const filename = pdfFilename(postState);
  const superLikesLabel = "Superaprecieri";
  const likesLabel = "Aprecieri";
  const viewsLabel = "Vizualizări";
  const commentsLabel = "Comentarii";
  const downloadLabel = "Descarcă PDF";
  const superLikesCount = formatNumber(postState.super_likes_count);
  const likesCount = formatNumber(postState.likes_count);
  const viewsCount = formatNumber(postState.view_count ?? postState.vizualizari);
  const commentsCountLabel = formatNumber(commentsCount);
  const ownPost = Boolean(user?.id && postState.user_id && Number(postState.user_id) === Number(user.id));
  const liked = Boolean(postState.viewer_liked) && !ownPost;
  const ownPostLikeMessage = "Nu poți aprecia propria postare.";
  const ownPostSuperLikeMessage = "Nu îți poți super-aprecia propria postare.";

  const updatePost = (updater) => {
    const next = updater(postState);
    setPostState(next);
    onPostChange?.(next);
  };

  const showLoginModal = (message = "Pentru această acțiune trebuie să intri în cont.") => {
    setStatus("");
    setModal(null);
    openAuthModal?.({ message, postId: postState?.id });
  };

  const handleLike = async () => {
    if (ownPost) {
      setStatus(ownPostLikeMessage);
      return;
    }
    if (liked) {
      setStatus("Ai apreciat deja acest text.");
      return;
    }
    setBusy("like");
    setStatus("");
    try {
      await likePost(postState.id);
      updatePost((current) => ({
        ...current,
        viewer_liked: true,
        likes_count: (current.likes_count ?? 0) + 1
      }));
    } catch (requestError) {
      if (requestError.status === 409) {
        updatePost((current) => ({
          ...current,
          viewer_liked: true,
          likes_count: Math.max(1, current.likes_count ?? 0)
        }));
        setStatus("Ai apreciat deja acest text.");
      } else {
        setStatus(requestError.message || "Nu am putut salva aprecierea.");
      }
    } finally {
      setBusy("");
    }
  };

  const handleSuperLike = async () => {
    if (!user) {
      showLoginModal("Pentru super-apreciere trebuie să intri în cont.");
      return;
    }
    if (ownPost) {
      setStatus(ownPostSuperLikeMessage);
      return;
    }
    if (postState.viewer_super_liked) {
      setStatus("Ai super-apreciat deja acest text.");
      return;
    }
    setBusy("super");
    setStatus("");
    try {
      await addSuperLike(postState.id);
      updatePost((current) => ({
        ...current,
        viewer_super_liked: true,
        super_likes_count: (current.super_likes_count ?? 0) + 1
      }));
    } catch (requestError) {
      if (requestError.status === 409) {
        updatePost((current) => ({
          ...current,
          viewer_super_liked: true,
          super_likes_count: Math.max(1, current.super_likes_count ?? 0)
        }));
        setStatus("Ai super-apreciat deja acest text.");
      } else {
        setModal({
          kicker: "super-apreciez",
          title: "Super-apreciere indisponibilă",
          message: requestError.message || "Nu am putut salva super-aprecierea.",
          actionHref: requestError.status === 403 ? mainPath("/premium") : null,
          actionLabel: "Vezi Premium"
        });
      }
    } finally {
      setBusy("");
    }
  };

  const openReportModal = () => {
    if (!user) {
      showLoginModal("Pentru raportări trebuie să intri în cont.");
      return;
    }
    setStatus("");
    setReportDetails("");
    setReportEvidenceUrl("");
    setReportModal({});
  };

  const selectReportReason = (reasonType) => {
    setReportDetails("");
    setReportEvidenceUrl("");
    setReportModal({ reasonType });
  };

  const closeReportModal = () => {
    if (busy === "report") return;
    setReportModal(null);
    setReportDetails("");
    setReportEvidenceUrl("");
  };

  const submitReport = async (event) => {
    event.preventDefault();
    if (!reportModal) return;
    setBusy("report");
    setStatus("");
    try {
      await reportPost(postState.id, {
        reason_type: reportModal.reasonType,
        details: reportDetails,
        evidence_url: reportModal.reasonType === "plagiarism" ? reportEvidenceUrl : ""
      });
      setStatus("Raportarea a fost trimisă către moderatori.");
      setReportModal(null);
      setReportDetails("");
      setReportEvidenceUrl("");
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut trimite raportarea.");
    } finally {
      setBusy("");
    }
  };

  const applyCommentReactionSummary = (commentId, summary) => {
    updatePost((current) => ({
      ...current,
      approved_comments: (Array.isArray(current.approved_comments) ? current.approved_comments : []).map((comment) => (
        comment.id === commentId
          ? {
              ...comment,
              reaction_counts: summary.counts || comment.reaction_counts || {},
              reaction_total: summary.total ?? comment.reaction_total ?? 0,
              viewer_reaction: summary.viewer_reaction || null
            }
          : comment
      ))
    }));
  };

  const handleCommentReaction = async (comment, reactionType) => {
    if (!user) {
      showLoginModal("Pentru reacții la comentarii trebuie să intri în cont.");
      return;
    }
    if (comment.user_id === user.id) {
      setStatus("Nu poți reacționa la propriul comentariu.");
      return;
    }
    const active = comment.viewer_reaction === reactionType;
    setBusy(`comment-reaction:${comment.id}:${reactionType}`);
    setStatus("");
    try {
      const summary = active
        ? await removeCommentReaction(comment.id)
        : await reactToComment(comment.id, reactionType);
      applyCommentReactionSummary(comment.id, summary);
    } catch (requestError) {
      if (requestError.status === 401) {
        showLoginModal("Pentru reacții la comentarii trebuie să intri în cont.");
      } else {
        setStatus(requestError.message || "Nu am putut salva reacția la comentariu.");
      }
    } finally {
      setBusy("");
    }
  };

  const submitComment = async (event, { skipDiacritics = false } = {}) => {
    event?.preventDefault();
    if (!user) {
      showLoginModal("Pentru comentarii trebuie să intri în cont.");
      return;
    }
    const content = commentText.trim();
    const visibleContent = htmlToText(content);
    if (!visibleContent) return;
    if (visibleContent.length > COMMENT_CHARACTER_LIMIT) {
      setStatus(`Comentariul poate avea cel mult ${formatNumber(COMMENT_CHARACTER_LIMIT)} de caractere.`);
      return;
    }
    setBusy("comment");
    setStatus("");
    try {
      if (!skipDiacritics && user && commentAutoDiacritics && !commentReview) {
        startDiacriticsProgress({ content });
        const converted = await addDiacritics({ kind: "comment", content });
        finishDiacriticsProgress();
        applyDiacriticsQuota(converted.quota);
        setCommentText(converted.content);
        setCommentReview({ originalContent: commentText, changed: converted.changed });
        return;
      }
      const createdComment = await createComment(postState.id, { content });
      const localComment = {
        ...createdComment,
        reaction_counts: createdComment.reaction_counts || {},
        reaction_total: createdComment.reaction_total || 0,
        viewer_reaction: createdComment.viewer_reaction || null,
        user: createdComment.user || (user ? {
          id: user.id,
          username: user.username,
          avatar_seed: user.avatar_seed,
          avatar_url: user.avatar_url,
          is_premium: user.is_premium,
          premium_tier: user.premium_tier
        } : null)
      };
      setPostState((current) => {
        const currentComments = Array.isArray(current.approved_comments) ? current.approved_comments : [];
        if (currentComments.some((comment) => comment.id === localComment.id)) return current;
        const next = {
          ...current,
          approved_comments: [...currentComments, localComment],
          comments_count: Number(current.comments_count || 0) + 1
        };
        onPostChange?.(next);
        return next;
      });
      setCommentText("");
      setCommentReview(null);
      setStatus("");
    } catch (requestError) {
      failDiacriticsProgress();
      setStatus(requestError.message || "Nu am putut trimite comentariul.");
    } finally {
      setBusy("");
    }
  };

  const audioAvailable = Boolean(audioState.data?.available && audioState.data?.playback_url);
  const canAddToPlaylist = Boolean(user?.has_author_audio_access && audioAvailable);
  const hasPanelContent = Boolean(audioState.error || commentOpen || status);

  return (
    <div className={`post-action-tools landing-post-tools ${className}`.trim()}>
      <div className="piece-actions post-engagement-row" aria-label="Acțiuni text">
        <button className={`react-btn react-super ${postState.viewer_super_liked && !ownPost ? "on" : ""}`} type="button" onClick={handleSuperLike} disabled={ownPost || Boolean(postState.viewer_super_liked) || busy === "super"} aria-pressed={Boolean(postState.viewer_super_liked) && !ownPost} aria-label={`${superLikesLabel}: ${superLikesCount}${ownPost ? `. ${ownPostSuperLikeMessage}` : postState.viewer_super_liked ? ". Ai super-apreciat deja acest text." : ""}`} title={ownPost ? ownPostSuperLikeMessage : postState.viewer_super_liked ? "Ai super-apreciat deja acest text" : superLikesLabel}>
          <FaHeart className="react-symbol" aria-hidden="true" focusable="false" />
          <MetricCount value={superLikesCount} />
        </button>
        <button className={`react-btn react-like ${liked ? "on" : ""}`} type="button" onClick={handleLike} disabled={ownPost || liked || busy === "like"} aria-pressed={liked} aria-label={`${likesLabel}: ${likesCount}${ownPost ? `. ${ownPostLikeMessage}` : liked ? ". Ai apreciat deja acest text." : ""}`} title={ownPost ? ownPostLikeMessage : liked ? "Ai apreciat deja acest text" : likesLabel}>
          <FaHeart className="react-symbol" aria-hidden="true" focusable="false" />
          <MetricCount value={likesCount} />
        </button>
        <span className="react-btn react-stat" title={viewsLabel} aria-label={`${viewsLabel}: ${viewsCount}`}>
          <FiEye className="react-symbol" aria-hidden="true" focusable="false" />
          <MetricCount value={viewsCount} />
        </span>
        <button className="react-btn react-comments" type="button" onClick={() => setCommentOpen((open) => !open)} aria-expanded={commentOpen} aria-controls={`comments-${postState.id}`} aria-label={`${commentsLabel}: ${commentsCountLabel}`} title={commentsLabel}>
          <FiMessageCircle className="react-symbol" aria-hidden="true" focusable="false" />
          <MetricCount value={commentsCountLabel} />
        </button>
        <a className="react-btn react-link post-pdf-download" href={pdfHref} download={filename} aria-label={downloadLabel} title={downloadLabel}>
          <FiDownload aria-hidden="true" focusable="false" />
        </a>
        <button className="react-btn react-report-trigger" type="button" onClick={openReportModal} disabled={busy === "report"} aria-label="Raportează" title="Raportează">
          <FaFlag aria-hidden="true" />
        </button>
        {canAddToPlaylist ? (
          <button className="react-btn react-playlist-trigger" type="button" onClick={openPlaylistModal} disabled={String(busy).startsWith("playlist")} aria-label="Adaugă în playlist" title="Adaugă în playlist">
            <FiList aria-hidden="true" />
          </button>
        ) : null}
        <div className="post-audio-inline">
          {audioAvailable ? (
            <CompactAudioPlayer
              src={audioState.data.playback_url}
              audioId={audioState.data.audio_id}
              listenMode={postState.category}
              showDownload={false}
            />
          ) : (
            <CompactAudioPlayer
              src=""
              showDownload={false}
              className="post-audio-placeholder"
              disabledTitle={audioState.loading ? "Se verifică fișierul audio..." : NO_AUDIO_TITLE}
            />
          )}
        </div>
      </div>

      {hasPanelContent ? (
        <div className="post-action-floating-panels">
          {audioState.error ? <div className="inline-error post-audio-error-row">{audioState.error}</div> : null}

          {commentOpen ? (
            <CommentPanel
              post={postState}
              user={user}
              busy={busy}
              commentText={commentText}
              commentAutoDiacritics={commentAutoDiacritics}
              commentReview={commentReview}
              diacriticsQuota={diacriticsQuota}
              diacriticsQuotaLoading={diacriticsQuotaLoading}
              diacriticsQuotaError={diacriticsQuotaError}
              onCommentTextChange={setCommentText}
              onCommentAutoDiacriticsChange={setCommentAutoDiacritics}
              onCommentReviewChange={setCommentReview}
              onLoginRequired={() => showLoginModal("Pentru comentarii trebuie să intri în cont.")}
              onReactToComment={handleCommentReaction}
              onSubmit={submitComment}
              submitButtonRef={commentSubmitRef}
            />
          ) : null}

          {status ? <div className="inline-error">{status}</div> : null}
        </div>
      ) : null}
      <DiacriticsProgressOverlay {...diacriticsProgress} />
      <AccessModal modal={modal} onClose={() => setModal(null)} />
      <PlaylistModal
        open={playlistModalOpen}
        loading={playlistLoading}
        playlists={playlistOptions}
        addedIds={playlistAddedIds}
        status={playlistStatus}
        busy={String(busy).startsWith("playlist") ? busy : ""}
        title={newPlaylistTitle}
        onTitleChange={setNewPlaylistTitle}
        onClose={() => setPlaylistModalOpen(false)}
        onReload={loadPlaylistOptions}
        onAdd={addCurrentPostToPlaylist}
        onCreate={createPlaylistAndAddPost}
      />
      <ReportModal
        modal={reportModal}
        busy={busy}
        details={reportDetails}
        evidenceUrl={reportEvidenceUrl}
        onDetailsChange={setReportDetails}
        onEvidenceUrlChange={setReportEvidenceUrl}
        onSelectReason={selectReportReason}
        onClose={closeReportModal}
        onSubmit={submitReport}
      />
    </div>
  );
}
