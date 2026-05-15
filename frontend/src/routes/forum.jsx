import { useEffect, useState } from "react";
import { createForumReply, createForumThread, fetchForumThread, fetchForumThreads } from "../api/forum.js";
import { searchUsers } from "../api/users.js";
import { addDiacritics } from "../api/writing.js";
import { FORUM_MODERATION_MESSAGE, FORUM_SECTIONS, TITLE_CHARACTER_LIMIT } from "../app/constants.js";
import { AuthorLink, RichTextContent } from "../app/content.jsx";
import { DiacriticsControl, DiacriticsProgressOverlay, DiacriticsReviewPanel, diacriticsSubmitLabel, useDiacriticsProgress } from "../app/diacritics.jsx";
import { RichTextEditor } from "../app/editor.jsx";
import { formatDateTime, forumSectionLabel, htmlToText } from "../app/format.js";
import { useAsync } from "../app/hooks.js";
import { ActionRow, AuthRequired, PageShell, StatusPanel } from "../app/layout.jsx";
import { mainPath } from "../app/paths.js";

function ForumListView({ user }) {
  const [section, setSection] = useState("general");
  const { data, error, loading } = useAsync(
    () => (user ? fetchForumThreads(section) : Promise.resolve({ threads: [] })),
    [user?.id, section]
  );

  if (!user) return <AuthRequired className="forum-page" />;

  return (
    <PageShell
      kicker="discuții"
      title="Discuții"
      sub="Discuții pentru întrebări, feedback și conversații între autori."
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
                active={section === item.key}
                onClick={() => setSection(item.key)}
              />
            ))}
          </div>
          <a className="cal-btn primary" href={mainPath("/discutii/nou")}>Discuție nouă</a>
        </aside>
      }
    >
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca forumul">{error}</StatusPanel> : null}
      {data?.threads?.length ? (
        <div className="list-grid">
          {data.threads.map((thread) => (
            <article className="piece-card" key={thread.id}>
              <div className="piece-card-kicker">{forumSectionLabel(thread.section)}</div>
              <h2 className="piece-card-title">
                <a className="post-title-link" href={mainPath(`/discutii/${thread.slug}`)}>{thread.title}</a>
              </h2>
              <div className="piece-card-meta">
                {thread.author?.username ? <AuthorLink user={thread.author} /> : null}
                <span>{thread.reply_count} răspunsuri</span>
                {thread.last_activity_at ? <span>{formatDateTime(thread.last_activity_at)}</span> : null}
              </div>
            </article>
          ))}
        </div>
      ) : !loading && !error ? <StatusPanel title="Nu există thread-uri aici" /> : null}
    </PageShell>
  );
}
function ForumThreadCreateView({ user }) {
  const [section, setSection] = useState("general");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [status, setStatus] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [autoDiacritics, setAutoDiacritics] = useState(Boolean(user?.is_premium));
  const [diacriticsReview, setDiacriticsReview] = useState(null);
  const {
    diacriticsProgress,
    startDiacriticsProgress,
    finishDiacriticsProgress,
    failDiacriticsProgress
  } = useDiacriticsProgress();

  useEffect(() => {
    setAutoDiacritics(Boolean(user?.is_premium));
    setDiacriticsReview(null);
  }, [user?.id, user?.is_premium]);

  if (!user) return <AuthRequired className="forum-page" />;

  const submit = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setStatus("");
    if (!title.trim() || !htmlToText(content)) {
      setStatus("Titlul și mesajul sunt obligatorii.");
      setSubmitting(false);
      return;
    }
    try {
      if (user.is_premium && autoDiacritics && !diacriticsReview) {
        startDiacriticsProgress({ title, content });
        const converted = await addDiacritics({ kind: "forum_thread", title, content });
        finishDiacriticsProgress();
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
            enabled: Boolean(user.is_premium && autoDiacritics),
            submitLabel: "Publică thread"
          })}
        </button>
      </form>
    </PageShell>
  );
}
function ForumThreadDetailView({ user, slug }) {
  const [reply, setReply] = useState("");
  const [status, setStatus] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [replyAutoDiacritics, setReplyAutoDiacritics] = useState(Boolean(user?.is_premium));
  const [replyReview, setReplyReview] = useState(null);
  const {
    diacriticsProgress,
    startDiacriticsProgress,
    finishDiacriticsProgress,
    failDiacriticsProgress
  } = useDiacriticsProgress();
  const { data, error, loading } = useAsync(
    () => (user ? fetchForumThread(slug) : Promise.resolve(null)),
    [user?.id, slug, refreshKey]
  );

  useEffect(() => {
    setReplyAutoDiacritics(Boolean(user?.is_premium));
    setReplyReview(null);
  }, [user?.id, user?.is_premium, slug]);

  if (!user) return <AuthRequired className="forum-page" />;

  const submitReply = async (event) => {
    event.preventDefault();
    if (!data) return;
    const content = reply.trim();
    if (!htmlToText(content)) return;
    setSubmitting(true);
    setStatus("");
    try {
      if (user.is_premium && replyAutoDiacritics && !replyReview) {
        startDiacriticsProgress({ content });
        const converted = await addDiacritics({ kind: "forum_reply", content });
        finishDiacriticsProgress();
        setReply(converted.content);
        setReplyReview({ originalContent: reply, changed: converted.changed });
        setSubmitting(false);
        return;
      }
      const created = await createForumReply(data.id, { content });
      setReply("");
      setReplyReview(null);
      setStatus(created.moderation_status === "approved" ? "" : FORUM_MODERATION_MESSAGE);
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
          {data.moderation_status !== "approved" ? (
            <StatusPanel title="Mesaj în curs de moderare">{FORUM_MODERATION_MESSAGE}</StatusPanel>
          ) : null}
          <article className="forum-post">
            <div className="piece-card-meta">
              {data.author?.username ? <AuthorLink user={data.author} /> : <span>anonim</span>}
              <span>{formatDateTime(data.created_at)}</span>
              {data.moderation_status !== "approved" ? <span>{data.moderation_status}</span> : null}
            </div>
            <RichTextContent html={data.content} className="forum-body" />
          </article>
          <section className="forum-replies" aria-label="Răspunsuri">
            <div className="piece-card-kicker">răspunsuri</div>
            {data.replies?.length ? (
              <div className="reply-list">
                {data.replies.map((item) => (
                  <article className="forum-reply" id={`reply-${item.id}`} key={item.id}>
                    <div className="piece-card-meta">
                      {item.author?.username ? <AuthorLink user={item.author} /> : <span>anonim</span>}
                      <span>{formatDateTime(item.created_at)}</span>
                      {item.moderation_status !== "approved" ? <span>{item.moderation_status}</span> : null}
                    </div>
                    <RichTextContent html={item.content} className="forum-body" />
                  </article>
                ))}
              </div>
            ) : <p className="auth-sub">Nu există răspunsuri încă.</p>}
          </section>
          {data.is_locked ? (
            <StatusPanel title="Discuție închisă">Nu mai pot fi adăugate răspunsuri.</StatusPanel>
          ) : (
            <form className="form-stack" onSubmit={submitReply}>
              <label className="auth-field" htmlFor="forum-reply">Răspuns</label>
              <RichTextEditor id="forum-reply" value={reply} onChange={setReply} maxLength={4000} mentionSearch={searchUsers} />
              <DiacriticsControl
                user={user}
                enabled={replyAutoDiacritics}
                disabled={Boolean(replyReview)}
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
                  enabled: Boolean(user.is_premium && replyAutoDiacritics),
                  submitLabel: "Răspunde"
                })}
              </button>
            </form>
          )}
        </div>
      ) : null}
    </PageShell>
  );
}

export default function ForumRoute({ route, user }) {
  if (route.name === "forumCreate") return <ForumThreadCreateView user={user} />;
  if (route.name === "forumThread") return <ForumThreadDetailView user={user} slug={route.slug} />;
  return <ForumListView user={user} />;
}
