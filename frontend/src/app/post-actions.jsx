import { useEffect, useState } from "react";
import { FiDownload } from "react-icons/fi";
import { AUTH_GOOGLE_PATH } from "../api/auth.js";
import { fetchPostAudioStatus } from "../api/audio.js";
import { createComment, likePost } from "../api/posts.js";
import { addSuperLike, removeSuperLike } from "../api/super-likes.js";
import { searchUsers } from "../api/users.js";
import { addDiacritics } from "../api/writing.js";
import { COMMENT_CHARACTER_LIMIT, COMMENT_MODERATION_MESSAGE } from "./constants.js";
import { CompactAudioPlayer, RichTextContent } from "./content.jsx";
import { DiacriticsControl, DiacriticsProgressOverlay, DiacriticsReviewPanel, diacriticsSubmitLabel, useDiacriticsProgress } from "./diacritics.jsx";
import { RichTextEditor } from "./editor.jsx";
import { formatDateTime, formatNumber, htmlToText, usernameHandle } from "./format.js";
import { mainPath } from "./paths.js";

const NO_AUDIO_TITLE = "Utilizatorul nu a convertit inca textul in fisier audio";

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

function pdfFilename(post) {
  const stem = String(post?.slug || "calimara-export").replace(/\.pdf$/i, "").trim();
  return `${stem || "calimara-export"}.pdf`;
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
          <a className="cal-btn primary" href={AUTH_GOOGLE_PATH}>Autentifică-te ca să comentezi</a>
        </div>
      )}
    </div>
  );
}

export function PostActionTools({ post, user, onPostChange, pdfHref = "#", className = "" }) {
  const [postState, setPostState] = useState(post);
  const [liked, setLiked] = useState(false);
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");
  const [modal, setModal] = useState(null);
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

  const updatePost = (updater) => {
    setPostState((current) => {
      const next = updater(current || postState);
      onPostChange?.(next);
      return next;
    });
  };

  const showLoginModal = (message = "Pentru această acțiune trebuie să intri în cont.") => {
    setModal({
      title: "Autentificare necesară",
      message,
      actionHref: AUTH_GOOGLE_PATH,
      actionLabel: "Autentifică-te"
    });
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

  return (
    <div className={`post-action-tools landing-post-tools ${className}`.trim()}>
      <div className="piece-actions post-engagement-row" aria-label="Acțiuni text">
        <button className={`react-btn react-super ${postState.viewer_super_liked ? "on" : ""}`} type="button" onClick={handleSuperLike} disabled={busy === "super"} aria-pressed={Boolean(postState.viewer_super_liked)}>
          Super-aprecieri
          <span className="react-count">{formatNumber(postState.super_likes_count)}</span>
        </button>
        <button className={`react-btn react-like ${liked ? "on" : ""}`} type="button" onClick={handleLike} disabled={busy === "like"} aria-pressed={liked}>
          Aprecieri
          <span className="react-count">{formatNumber(postState.likes_count)}</span>
        </button>
        <span className="react-btn react-stat" title="Vizualizari unice">
          Vizualizari unice
          <span className="react-count">{formatNumber(postState.view_count ?? postState.vizualizari)}</span>
        </span>
        <button className="react-btn" type="button" onClick={() => setCommentOpen((open) => !open)} aria-expanded={commentOpen} aria-controls={`comments-${postState.id}`}>
          Comentarii
          <span className="react-count">{formatNumber(commentsCount)}</span>
        </button>
        <a className="react-btn react-link post-pdf-download" href={pdfHref} download={filename}>
          <FiDownload aria-hidden="true" />
          <span>{filename}</span>
        </a>
      </div>

      <div className="post-audio-row">
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
        {audioState.error ? <div className="inline-error">{audioState.error}</div> : null}
      </div>

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
          onSubmit={submitComment}
        />
      ) : null}

      {status ? <div className="inline-error">{status}</div> : null}
      <DiacriticsProgressOverlay {...diacriticsProgress} />
      <AccessModal modal={modal} onClose={() => setModal(null)} />
    </div>
  );
}
