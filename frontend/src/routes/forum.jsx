import { useEffect, useState } from "react";
import { FaFlag } from "react-icons/fa";
import { createForumReply, createForumThread, fetchForumThread, fetchForumThreads, reportForumReply, reportForumThread } from "../api/forum.js";
import { searchUsers } from "../api/users.js";
import { addDiacritics } from "../api/writing.js";
import { useAuthModal } from "../app/auth-modal.jsx";
import { FORUM_SECTIONS, MODERATING_STATUSES, TEXT_MODERATION_MESSAGE, TITLE_CHARACTER_LIMIT } from "../app/constants.js";
import { AuthorLink, ModerationOverlay, RichTextContent } from "../app/content.jsx";
import { DiacriticsControl, DiacriticsProgressOverlay, DiacriticsReviewPanel, diacriticsSubmitLabel, useDiacriticsProgress, useDiacriticsQuota } from "../app/diacritics.jsx";
import { RichTextEditor } from "../app/editor.jsx";
import { formatDateTime, formatGologani, formatNumber, forumSectionLabel, htmlToText } from "../app/format.js";
import { useAsync } from "../app/hooks.js";
import { ActionRow, AuthRequired, PageShell, StatusPanel } from "../app/layout.jsx";
import { mainPath, profileAvatarUrl } from "../app/paths.js";
import { ReportModal } from "../app/post-actions.jsx";

function ForumAuthorPanel({ author }) {
  if (!author?.username) {
    return (
      <aside className="forum-author-panel">
        <span className="forum-author-name">anonim</span>
      </aside>
    );
  }

  return (
    <aside className="forum-author-panel" aria-label={`Autor ${author.username}`}>
      <img className="forum-author-avatar profile-picture" src={profileAvatarUrl(author, 96)} alt="" aria-hidden="true" />
      <AuthorLink user={author} className="forum-author-name author-link" />
      <dl className="forum-author-stats" aria-label="Statistici autor">
        <div>
          <dt>forum</dt>
          <dd>{formatNumber(author.forum_post_count)}</dd>
        </div>
        <div>
          <dt>Gologani</dt>
          <dd>{formatGologani(author.gologani_balance)}</dd>
        </div>
        <div>
          <dt>publicate</dt>
          <dd>{formatNumber(author.published_post_count)}</dd>
        </div>
      </dl>
    </aside>
  );
}

function ForumMessage({ item, isThread = false, user, authLoaded = true, onReport, reportBusy = false }) {
  const isModerating = MODERATING_STATUSES.has(item.moderation_status);
  const canReport = item.moderation_status === "approved";
  return (
    <article className={`${isThread ? "forum-post" : "forum-reply"} ${isModerating ? "has-moderation-overlay" : ""}`.trim()} id={isThread ? undefined : `reply-${item.id}`}>
      <ForumAuthorPanel author={item.author} />
      <div className={`forum-message-content ${canReport ? "has-report-action" : ""}`.trim()}>
        <div className="piece-card-meta">
          <span>{formatDateTime(item.created_at)}</span>
        </div>
        <div className={`forum-body-wrap ${isModerating ? "has-moderation-overlay" : ""}`.trim()}>
          <RichTextContent html={item.content} className="forum-body" />
          {isModerating ? (
            <ModerationOverlay className="forum-moderation-overlay">{TEXT_MODERATION_MESSAGE}</ModerationOverlay>
          ) : null}
        </div>
        {canReport ? (
          <button className="forum-report-btn" type="button" disabled={!authLoaded || Boolean(reportBusy)} onClick={() => onReport?.({ type: isThread ? "forum_thread" : "forum_reply", item })} title={user ? "Raportează" : "Autentifică-te pentru raportare"} aria-label={user ? "Raportează" : "Autentifică-te pentru raportare"}>
            <FaFlag aria-hidden="true" />
          </button>
        ) : null}
      </div>
    </article>
  );
}

function isForumSectionKey(value) {
  return FORUM_SECTIONS.some((item) => item.key === value);
}

function forumCreateHref(section) {
  const query = isForumSectionKey(section) ? `?section=${encodeURIComponent(section)}` : "";
  return mainPath(`/discutii/nou${query}`);
}

function initialForumSection() {
  if (typeof window === "undefined") return "general";
  const requestedSection = new URLSearchParams(window.location.search).get("section");
  return isForumSectionKey(requestedSection) ? requestedSection : "general";
}

function ForumListView({ user, authLoaded }) {
  const [section, setSection] = useState("general");
  const { openAuthModal } = useAuthModal();
  const { data, error, loading } = useAsync(
    () => fetchForumThreads(section),
    [section]
  );

  const createHref = forumCreateHref(section);
  const newThreadAction = user ? (
    <a className="cal-btn primary" href={createHref}>Discuție nouă</a>
  ) : (
    <button
      className="cal-btn primary"
      type="button"
      disabled={!authLoaded}
      onClick={() => openAuthModal?.({ returnTo: createHref })}
    >
      Discuție nouă
    </button>
  );

  return (
    <PageShell
      kicker="discuții"
      title="Discuții"
      sub="Discuții pentru întrebări și conversații între autori."
      className="forum-page"
      side={
        <aside className="side-col">
          <div className="side-kicker">secțiuni</div>
          <div className="actions-group">
            {FORUM_SECTIONS.map((item, index) => (
              <ActionRow
                key={item.key}
                number={String(index + 1).padStart(2, "0")}
                label={item.label}
                className={item.featured ? "forum-section-featured" : ""}
                active={section === item.key}
                onClick={() => setSection(item.key)}
              />
            ))}
          </div>
          {newThreadAction}
        </aside>
      }
    >
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca forumul">{error}</StatusPanel> : null}
      {data?.threads?.length ? (
        <div className="list-grid">
          {data.threads.filter((thread) => thread.moderation_status !== "rejected").map((thread) => {
            const isModerating = MODERATING_STATUSES.has(thread.moderation_status);
            return (
              <article className={`piece-card forum-thread-card ${isModerating ? "has-moderation-overlay" : ""}`.trim()} key={thread.id}>
                <div className="forum-thread-card-content">
                  <div className="piece-card-kicker">{forumSectionLabel(thread.section)}</div>
                  <h2 className="piece-card-title">
                    <a className="post-title-link" href={mainPath(`/discutii/${thread.slug}`)}>{thread.title}</a>
                  </h2>
                  <div className="piece-card-meta">
                    {thread.author?.username ? <AuthorLink user={thread.author} /> : null}
                    <span>{thread.reply_count} răspunsuri</span>
                    {thread.last_activity_at ? <span>{formatDateTime(thread.last_activity_at)}</span> : null}
                  </div>
                </div>
                {isModerating ? (
                  <ModerationOverlay className="forum-card-moderation-overlay">{TEXT_MODERATION_MESSAGE}</ModerationOverlay>
                ) : null}
              </article>
            );
          })}
        </div>
      ) : !loading && !error ? <StatusPanel title="Nu există thread-uri aici" /> : null}
    </PageShell>
  );
}
function ForumThreadCreateView({ user }) {
  const [section, setSection] = useState(initialForumSection);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [status, setStatus] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [autoDiacritics, setAutoDiacritics] = useState(false);
  const [diacriticsReview, setDiacriticsReview] = useState(null);
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
    setAutoDiacritics(false);
    setDiacriticsReview(null);
  }, [user?.id]);

  if (!user) return <AuthRequired className="forum-page" />;

  const submit = async (event, { skipDiacritics = false } = {}) => {
    event?.preventDefault();
    setSubmitting(true);
    setStatus("");
    if (!title.trim() || !htmlToText(content)) {
      setStatus("Titlul și mesajul sunt obligatorii.");
      setSubmitting(false);
      return;
    }
    try {
      if (!skipDiacritics && user && autoDiacritics && !diacriticsReview) {
        startDiacriticsProgress({ title, content });
        const converted = await addDiacritics({ kind: "forum_thread", title, content });
        finishDiacriticsProgress();
        applyDiacriticsQuota(converted.quota);
        setTitle(converted.title ?? title);
        setContent(converted.content);
        setDiacriticsReview({
          originalTitle: title,
          originalContent: content,
          changed: converted.changed
        });
        setSubmitting(false);
        return;
      }
      const thread = await createForumThread({ section, title, content });
      window.location.href = mainPath(`/discutii/${thread.slug}`);
    } catch (requestError) {
      failDiacriticsProgress();
      setStatus(requestError.message || "Nu am putut publica discuția.");
      setSubmitting(false);
    }
  };

  return (
    <PageShell kicker="discuții" title="Discuție nouă" sub="Deschide o discuție în forum." className="forum-page">
      <DiacriticsProgressOverlay {...diacriticsProgress} />
      <form className="form-stack" onSubmit={submit}>
        <label className="auth-field" htmlFor="forum-section">Secțiune</label>
        <select id="forum-section" className="cal-input" value={section} onChange={(event) => setSection(event.target.value)}>
          {FORUM_SECTIONS.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
        </select>
        <label className="auth-field" htmlFor="forum-title">Titlu</label>
        <input id="forum-title" className="cal-input" value={title} onChange={(event) => setTitle(event.target.value)} maxLength={TITLE_CHARACTER_LIMIT} required />
        <label className="auth-field" htmlFor="forum-content">Mesaj</label>
        <RichTextEditor id="forum-content" className="tall" value={content} onChange={setContent} maxLength={8000} mentionSearch={searchUsers} />
        <DiacriticsControl
          user={user}
          enabled={autoDiacritics}
          disabled={Boolean(diacriticsReview)}
          quota={diacriticsQuota}
          quotaLoading={diacriticsQuotaLoading}
          quotaError={diacriticsQuotaError}
          onChange={(checked) => {
            setAutoDiacritics(checked);
            setDiacriticsReview(null);
          }}
        />
        <DiacriticsReviewPanel
          active={Boolean(diacriticsReview)}
          changed={Boolean(diacriticsReview?.changed)}
          onReset={diacriticsReview ? () => {
            setTitle(diacriticsReview.originalTitle);
            setContent(diacriticsReview.originalContent);
            setDiacriticsReview(null);
          } : null}
        />
        {status ? <div className="inline-error">{status}</div> : null}
        <button className="cal-btn primary" type="submit" disabled={submitting}>
          {diacriticsSubmitLabel({
            submitting,
            reviewing: Boolean(diacriticsReview),
            enabled: Boolean(user && autoDiacritics),
            submitLabel: "Publică thread"
          })}
        </button>
        {user && autoDiacritics && !diacriticsReview ? (
          <button className="cal-btn" type="button" onClick={() => submit(null, { skipDiacritics: true })} disabled={submitting}>
            Publică fără Diacritice
          </button>
        ) : null}
      </form>
    </PageShell>
  );
}
function ForumThreadDetailView({ user, authLoaded, slug }) {
  const [reply, setReply] = useState("");
  const [status, setStatus] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [replyAutoDiacritics, setReplyAutoDiacritics] = useState(false);
  const [replyReview, setReplyReview] = useState(null);
  const [reportModal, setReportModal] = useState(null);
  const [reportDetails, setReportDetails] = useState("");
  const [reportEvidenceUrl, setReportEvidenceUrl] = useState("");
  const [reportBusy, setReportBusy] = useState("");
  const [reportStatus, setReportStatus] = useState("");
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
  const { openAuthModal } = useAuthModal();
  const { data, error, loading } = useAsync(
    () => fetchForumThread(slug),
    [slug, refreshKey]
  );

  useEffect(() => {
    setReplyAutoDiacritics(false);
    setReplyReview(null);
    setReportModal(null);
    setReportDetails("");
    setReportEvidenceUrl("");
    setReportBusy("");
    setReportStatus("");
  }, [user?.id, slug]);

  const openReportModal = (target) => {
    if (!user) {
      openAuthModal?.({ returnTo: window.location.href });
      return;
    }
    setReportStatus("");
    setReportDetails("");
    setReportEvidenceUrl("");
    setReportModal({ target, reasonType: "offensive" });
  };

  const selectReportReason = (reasonType) => {
    setReportModal((current) => current ? { ...current, reasonType } : current);
    setReportDetails("");
    setReportEvidenceUrl("");
  };

  const closeReportModal = () => {
    if (reportBusy) return;
    setReportModal(null);
    setReportDetails("");
    setReportEvidenceUrl("");
  };

  const submitReport = async (event) => {
    event.preventDefault();
    if (!reportModal?.target?.item?.id || !reportModal.reasonType || reportBusy) return;
    const target = reportModal.target;
    setReportBusy("report");
    setReportStatus("");
    try {
      const payload = {
        reason_type: reportModal.reasonType,
        details: reportDetails,
        evidence_url: reportModal.reasonType === "plagiarism" ? reportEvidenceUrl : ""
      };
      if (target.type === "forum_thread") {
        await reportForumThread(target.item.id, payload);
      } else {
        await reportForumReply(target.item.id, payload);
      }
      setReportStatus("Raportarea a fost trimisă către moderatori.");
      setReportModal(null);
      setReportDetails("");
      setReportEvidenceUrl("");
    } catch (requestError) {
      setReportStatus(requestError.message || "Nu am putut trimite raportarea.");
    } finally {
      setReportBusy("");
    }
  };

  const submitReply = async (event, { skipDiacritics = false } = {}) => {
    event?.preventDefault();
    if (!data) return;
    const content = reply.trim();
    if (!htmlToText(content)) return;
    setSubmitting(true);
    setStatus("");
    try {
      if (!skipDiacritics && user && replyAutoDiacritics && !replyReview) {
        startDiacriticsProgress({ content });
        const converted = await addDiacritics({ kind: "forum_reply", content });
        finishDiacriticsProgress();
        applyDiacriticsQuota(converted.quota);
        setReply(converted.content);
        setReplyReview({ originalContent: reply, changed: converted.changed });
        setSubmitting(false);
        return;
      }
      const created = await createForumReply(data.id, { content });
      setReply("");
      setReplyReview(null);
      setStatus("");
      setRefreshKey((key) => key + 1);
    } catch (requestError) {
      failDiacriticsProgress();
      setStatus(requestError.message || "Nu am putut publica răspunsul.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <PageShell
      kicker={data ? forumSectionLabel(data.section) : "discuții"}
      title={data?.title ?? "Discuții"}
      sub={data?.author?.username ? <>Pornit de <AuthorLink user={data.author} /></> : ""}
      className="forum-page"
    >
      <DiacriticsProgressOverlay {...diacriticsProgress} />
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca discuția">{error}</StatusPanel> : null}
      {data ? (
        <div className="detail-stack">
          {reportStatus ? <div className="inline-status">{reportStatus}</div> : null}
          <ForumMessage item={data} isThread user={user} authLoaded={authLoaded} onReport={openReportModal} reportBusy={Boolean(reportBusy)} />
          <section className="forum-replies" aria-label="Răspunsuri">
            <div className="piece-card-kicker">răspunsuri</div>
            {data.replies?.length ? (
              <div className="reply-list">
                {data.replies.filter((item) => item.moderation_status !== "rejected").map((item) => (
                  <ForumMessage item={item} key={item.id} user={user} authLoaded={authLoaded} onReport={openReportModal} reportBusy={Boolean(reportBusy)} />
                ))}
              </div>
            ) : <p className="auth-sub">Nu există răspunsuri încă.</p>}
          </section>
          {data.is_locked ? (
            <StatusPanel title="Discuție închisă">Nu mai pot fi adăugate răspunsuri.</StatusPanel>
          ) : data.moderation_status !== "approved" ? null : user ? (
            <form className="form-stack" onSubmit={submitReply}>
              <label className="auth-field" htmlFor="forum-reply">Răspuns</label>
              <RichTextEditor id="forum-reply" value={reply} onChange={setReply} maxLength={4000} mentionSearch={searchUsers} />
              <DiacriticsControl
                user={user}
                enabled={replyAutoDiacritics}
                disabled={Boolean(replyReview)}
                quota={diacriticsQuota}
                quotaLoading={diacriticsQuotaLoading}
                quotaError={diacriticsQuotaError}
                onChange={(checked) => {
                  setReplyAutoDiacritics(checked);
                  setReplyReview(null);
                }}
              />
              <DiacriticsReviewPanel
                active={Boolean(replyReview)}
                changed={Boolean(replyReview?.changed)}
                onReset={replyReview ? () => {
                  setReply(replyReview.originalContent);
                  setReplyReview(null);
                } : null}
              />
              {status ? <div className="inline-error">{status}</div> : null}
              <button className="cal-btn primary" type="submit" disabled={submitting}>
                {diacriticsSubmitLabel({
                  submitting,
                  reviewing: Boolean(replyReview),
                  enabled: Boolean(user && replyAutoDiacritics),
                  submitLabel: "Răspunde"
                })}
              </button>
              {user && replyAutoDiacritics && !replyReview ? (
                <button className="cal-btn" type="button" onClick={() => submitReply(null, { skipDiacritics: true })} disabled={submitting}>
                  Răspunde fără Diacritice
                </button>
              ) : null}
            </form>
          ) : authLoaded ? (
            <StatusPanel
              title="Autentificare necesară"
              action={<button className="cal-btn primary" type="button" onClick={() => openAuthModal?.({ returnTo: window.location.href })}>Autentificare</button>}
            >
              Autentifică-te ca să răspunzi.
            </StatusPanel>
          ) : (
            <StatusPanel title="Se verifică sesiunea" />
          )}
          <ReportModal
            modal={reportModal}
            busy={reportBusy}
            details={reportDetails}
            evidenceUrl={reportEvidenceUrl}
            allowPlagiarism={false}
            onDetailsChange={setReportDetails}
            onEvidenceUrlChange={setReportEvidenceUrl}
            onSelectReason={selectReportReason}
            onClose={closeReportModal}
            onSubmit={submitReport}
          />
        </div>
      ) : null}
    </PageShell>
  );
}

export default function ForumRoute({ route, user, authLoaded }) {
  if (route.name === "forumCreate") return <ForumThreadCreateView user={user} />;
  if (route.name === "forumThread") return <ForumThreadDetailView user={user} authLoaded={authLoaded} slug={route.slug} />;
  return <ForumListView user={user} authLoaded={authLoaded} />;
}
