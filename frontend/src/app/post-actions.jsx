import { useCallback, useEffect, useRef, useState } from "react";
import { FaFlag, FaHeart } from "react-icons/fa";
import { FiChevronDown, FiDownload, FiEye, FiMessageCircle } from "react-icons/fi";
import { fetchPostAudioStatus } from "../api/audio.js";
import { createComment, likePost, reportPost } from "../api/posts.js";
import { addSuperLike, removeSuperLike } from "../api/super-likes.js";
import { promoteAuthor, promotePost, searchUsers } from "../api/users.js";
import { addDiacritics } from "../api/writing.js";
import { useAuthModal } from "./auth-modal.jsx";
import { COMMENT_CHARACTER_LIMIT, COMMENT_MODERATION_MESSAGE } from "./constants.js";
import { CompactAudioPlayer, RichTextContent } from "./content.jsx";
import { DiacriticsControl, DiacriticsProgressOverlay, DiacriticsReviewPanel, diacriticsSubmitLabel, useDiacriticsProgress } from "./diacritics.jsx";
import { RichTextEditor } from "./editor.jsx";
import { formatDateTime, formatNumber, htmlToText, usernameHandle } from "./format.js";
import { mainPath } from "./paths.js";

const NO_AUDIO_TITLE = "Utilizatorul nu a convertit încă textul în fișier audio";
const REPORT_TITLES = {
  offensive: "Raportează conținut ofensiv",
  plagiarism: "Raportează plagiat"
};

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

function ReportModal({
  modal,
  busy,
  details,
  evidenceUrl,
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
            <button className="report-choice-btn" type="button" onClick={() => onSelectReason("plagiarism")}>
              Raportează plagiat
            </button>
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

function pdfFilename(post) {
  const stem = String(post?.slug || "calimara-export").replace(/\.pdf$/i, "").trim();
  return `${stem || "calimara-export"}.pdf`;
}

export function PostPromotionMenu({ post, author, user }) {
  const menuRef = useRef(null);
  const buttonRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");
  const [panelStyle, setPanelStyle] = useState(null);

  const updatePanelPosition = useCallback(() => {
    const button = buttonRef.current;
    if (!button || typeof window === "undefined") return;

    const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 320;
    const edge = viewportWidth <= 520 ? 12 : 16;
    const preferredWidth = viewportWidth <= 520 ? 236 : 280;
    const panelWidth = Math.max(196, Math.min(preferredWidth, viewportWidth - edge * 2));
    const rect = button.getBoundingClientRect();
    const maxLeft = Math.max(edge, viewportWidth - panelWidth - edge);
    const left = Math.min(Math.max(rect.right - panelWidth, edge), maxLeft);

    setPanelStyle({
      position: "fixed",
      top: `${Math.max(edge, rect.bottom + 8)}px`,
      left: `${left}px`,
      right: "auto",
      width: `${panelWidth}px`,
      maxWidth: `calc(100vw - ${edge * 2}px)`,
      transform: "none"
    });
  }, []);

  useEffect(() => {
    setOpen(false);
    setBusy("");
    setStatus("");
    setPanelStyle(null);
  }, [post?.id, author?.id, user?.id]);

  useEffect(() => {
    if (!open) {
      setPanelStyle(null);
      return undefined;
    }

    let frame = window.requestAnimationFrame(updatePanelPosition);
    const scheduleUpdate = () => {
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(updatePanelPosition);
    };

    window.addEventListener("resize", scheduleUpdate);
    window.addEventListener("scroll", scheduleUpdate, true);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("resize", scheduleUpdate);
      window.removeEventListener("scroll", scheduleUpdate, true);
    };
  }, [open, updatePanelPosition]);

  useEffect(() => {
    if (!open) return undefined;
    const onPointerDown = (event) => {
      if (!menuRef.current || menuRef.current.contains(event.target)) return;
      setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
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

  return (
    <span className="title-promotion-menu" ref={menuRef}>
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
      {open ? (
        <span className="title-promotion-panel" role="menu" aria-label="Opțiuni de promovare" style={panelStyle || undefined}>
          <button className="title-promotion-option" type="button" role="menuitem" onClick={promoteCurrentPost} disabled={!user || Boolean(busy)}>
            {busy === "post" ? "Se promovează..." : "Promovează postarea pe profilul tău"}
          </button>
          <button className="title-promotion-option" type="button" role="menuitem" onClick={promoteCurrentAuthor} disabled={!user || Boolean(busy)}>
            {busy === "author" ? "Se promovează..." : "Promovează autorul pe profilul tău"}
          </button>
          {status ? <span className="title-promotion-status">{status}</span> : null}
        </span>
      ) : null}
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
  onCommentTextChange,
  onCommentAutoDiacriticsChange,
  onCommentReviewChange,
  onLoginRequired,
  onSubmit
}) {
  const comments = Array.isArray(post.approved_comments) ? post.approved_comments : [];
  const editorId = `post-comment-${post.id}`;

  return (
    <div className="piece-comments" id={`comments-${post.id}`}>
      {comments.length ? (
        <ul className="comment-list">
          {comments.map((comment) => {
            const author = comment.user?.username ? usernameHandle(comment.user.username) : comment.author_name || "cititor";
            return (
              <li className="comment" id={`comment-${comment.id}`} key={comment.id}>
                <div className="comment-head">
                  <span className="comment-author">{author}</span>
                  {comment.created_at ? <span className="comment-time">{formatDateTime(comment.created_at)}</span> : null}
                </div>
                <RichTextContent html={comment.content} className="comment-body" />
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="auth-sub post-comments-empty">Nu există comentarii aprobate încă.</p>
      )}

      {user ? (
        <form className="landing-comment-panel post-comment-form" onSubmit={onSubmit}>
          <label className="auth-field" htmlFor={editorId}>Comentariu</label>
          <RichTextEditor id={editorId} className="compact" value={commentText} onChange={onCommentTextChange} maxLength={COMMENT_CHARACTER_LIMIT} mentionSearch={searchUsers} />
          <DiacriticsControl
            user={user}
            enabled={commentAutoDiacritics}
            disabled={Boolean(commentReview)}
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
          <button className="cal-btn primary" type="submit" disabled={busy === "comment"}>
            {diacriticsSubmitLabel({
              submitting: busy === "comment",
              reviewing: Boolean(commentReview),
              enabled: Boolean(user?.is_premium && commentAutoDiacritics),
              submitLabel: "Trimite comentariul"
            })}
          </button>
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
  const [liked, setLiked] = useState(false);
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");
  const [modal, setModal] = useState(null);
  const [reportModal, setReportModal] = useState(null);
  const [reportDetails, setReportDetails] = useState("");
  const [reportEvidenceUrl, setReportEvidenceUrl] = useState("");
  const [audioState, setAudioState] = useState({ loading: false, data: null, error: "" });
  const [commentOpen, setCommentOpen] = useState(false);
  const [commentText, setCommentText] = useState("");
  const [commentAutoDiacritics, setCommentAutoDiacritics] = useState(Boolean(user?.is_premium));
  const [commentReview, setCommentReview] = useState(null);
  const {
    diacriticsProgress,
    startDiacriticsProgress,
    finishDiacriticsProgress,
    failDiacriticsProgress
  } = useDiacriticsProgress();

  useEffect(() => {
    setPostState(post);
    setLiked(false);
    setStatus("");
    setModal(null);
    setReportModal(null);
    setReportDetails("");
    setReportEvidenceUrl("");
    setCommentOpen(false);
    setCommentText("");
    setCommentReview(null);
  }, [post?.id, user?.id]);

  useEffect(() => {
    setCommentAutoDiacritics(Boolean(user?.is_premium));
    setCommentReview(null);
  }, [user?.id, user?.is_premium]);

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

  const updatePost = (updater) => {
    setPostState((current) => {
      const next = updater(current || postState);
      onPostChange?.(next);
      return next;
    });
  };

  const showLoginModal = (message = "Pentru această acțiune trebuie să intri în cont.") => {
    setStatus("");
    setModal(null);
    openAuthModal?.({ message, postId: postState?.id });
  };

  const handleLike = async () => {
    setBusy("like");
    setStatus("");
    try {
      await likePost(postState.id);
      setLiked(true);
      updatePost((current) => ({ ...current, likes_count: (current.likes_count ?? 0) + 1 }));
    } catch (requestError) {
      if (requestError.status === 409) {
        setLiked(true);
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
    setBusy("super");
    setStatus("");
    try {
      if (postState.viewer_super_liked) {
        await removeSuperLike(postState.id);
        updatePost((current) => ({
          ...current,
          viewer_super_liked: false,
          super_likes_count: Math.max(0, (current.super_likes_count ?? 0) - 1)
        }));
      } else {
        await addSuperLike(postState.id);
        updatePost((current) => ({
          ...current,
          viewer_super_liked: true,
          super_likes_count: (current.super_likes_count ?? 0) + 1
        }));
      }
    } catch (requestError) {
      setModal({
        kicker: "super-apreciez",
        title: "Super-apreciere indisponibilă",
        message: requestError.message || "Nu am putut salva super-aprecierea.",
        actionHref: requestError.status === 403 ? mainPath("/premium") : null,
        actionLabel: "Vezi Premium"
      });
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

  const submitComment = async (event) => {
    event.preventDefault();
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
      if (user?.is_premium && commentAutoDiacritics && !commentReview) {
        startDiacriticsProgress({ content });
        const converted = await addDiacritics({ kind: "comment", content });
        finishDiacriticsProgress();
        setCommentText(converted.content);
        setCommentReview({ originalContent: commentText, changed: converted.changed });
        return;
      }
      await createComment(postState.id, { content });
      setCommentText("");
      setCommentReview(null);
      setStatus(COMMENT_MODERATION_MESSAGE);
    } catch (requestError) {
      failDiacriticsProgress();
      setStatus(requestError.message || "Nu am putut trimite comentariul.");
    } finally {
      setBusy("");
    }
  };

  const audioAvailable = Boolean(audioState.data?.available && audioState.data?.playback_url);
  const hasPanelContent = Boolean(audioState.error || commentOpen || status);

  return (
    <div className={`post-action-tools landing-post-tools ${className}`.trim()}>
      <div className="piece-actions post-engagement-row" aria-label="Acțiuni text">
        <button className={`react-btn react-super ${postState.viewer_super_liked ? "on" : ""}`} type="button" onClick={handleSuperLike} disabled={busy === "super"} aria-pressed={Boolean(postState.viewer_super_liked)} aria-label={`${superLikesLabel}: ${superLikesCount}`} title={superLikesLabel}>
          <FaHeart className="react-symbol" aria-hidden="true" focusable="false" />
          <span className="react-count">{superLikesCount}</span>
        </button>
        <button className={`react-btn react-like ${liked ? "on" : ""}`} type="button" onClick={handleLike} disabled={busy === "like"} aria-pressed={liked} aria-label={`${likesLabel}: ${likesCount}`} title={likesLabel}>
          <FaHeart className="react-symbol" aria-hidden="true" focusable="false" />
          <span className="react-count">{likesCount}</span>
        </button>
        <span className="react-btn react-stat" title={viewsLabel} aria-label={`${viewsLabel}: ${viewsCount}`}>
          <FiEye className="react-symbol" aria-hidden="true" focusable="false" />
          <span className="react-count">{viewsCount}</span>
        </span>
        <button className="react-btn react-comments" type="button" onClick={() => setCommentOpen((open) => !open)} aria-expanded={commentOpen} aria-controls={`comments-${postState.id}`} aria-label={`${commentsLabel}: ${commentsCountLabel}`} title={commentsLabel}>
          <FiMessageCircle className="react-symbol" aria-hidden="true" focusable="false" />
          <span className="react-count">{commentsCountLabel}</span>
        </button>
        <a className="react-btn react-link post-pdf-download" href={pdfHref} download={filename} aria-label={downloadLabel} title={downloadLabel}>
          <FiDownload aria-hidden="true" focusable="false" />
        </a>
        <button className="react-btn react-report-trigger" type="button" onClick={openReportModal} disabled={busy === "report"} aria-label="Raportează" title="Raportează">
          <FaFlag aria-hidden="true" />
        </button>
        <div className="post-audio-inline">
          {audioAvailable ? (
            <CompactAudioPlayer src={audioState.data.playback_url} showDownload={false} />
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
              onCommentTextChange={setCommentText}
              onCommentAutoDiacriticsChange={setCommentAutoDiacritics}
              onCommentReviewChange={setCommentReview}
              onLoginRequired={() => showLoginModal("Pentru comentarii trebuie să intri în cont.")}
              onSubmit={submitComment}
            />
          ) : null}

          {status ? <div className="inline-error">{status}</div> : null}
        </div>
      ) : null}
      <DiacriticsProgressOverlay {...diacriticsProgress} />
      <AccessModal modal={modal} onClose={() => setModal(null)} />
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
