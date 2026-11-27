import { useEffect, useState } from "react";
import { FaFlag, FaLock, FaThumbtack } from "react-icons/fa";
import {
  createForumReply,
  createForumThread,
  fetchForumSections,
  fetchForumThread,
  fetchForumThreads,
  reportForumReply,
  reportForumThread,
  updateForumReplyState,
  updateForumThreadState
} from "../api/forum.js";
import { searchUsers } from "../api/users.js";
import { addDiacritics } from "../api/writing.js";
import { useAuthModal } from "../app/auth-modal.jsx";
import { MODERATING_STATUSES, TEXT_MODERATION_MESSAGE, TITLE_CHARACTER_LIMIT } from "../app/constants.js";
import { AuthorLink, ModerationOverlay, RichTextContent } from "../app/content.jsx";
import { DiacriticsControl, DiacriticsProgressOverlay, DiacriticsReviewPanel, diacriticsSubmitLabel, useDiacriticsProgress, useDiacriticsQuota } from "../app/diacritics.jsx";
import { RichTextEditor } from "../app/editor.jsx";
import { formatDateTime, formatGologani, formatNumber, forumSectionLabel, htmlToText } from "../app/format.js";
import { useAsync } from "../app/hooks.js";
import { ActionRow, AuthRequired, PageShell, StatusPanel } from "../app/layout.jsx";
import { mainPath, profileAvatarUrl } from "../app/paths.js";
import { ReportModal } from "../app/post-actions.jsx";

const THREAD_SORTS = [
  { key: "activity", label: "Activitate recentă" },
  { key: "newest", label: "Cele mai noi" },
  { key: "replies", label: "Cele mai multe răspunsuri" }
];

function queryParam(name) {
  if (typeof window === "undefined") return "";
  return new URLSearchParams(window.location.search).get(name) || "";
}

function queryPage() {
  const value = Number.parseInt(queryParam("pagina"), 10);
  return Number.isFinite(value) && value > 0 ? value : 1;
}

function hashReplyId() {
  if (typeof window === "undefined") return null;
  const match = /^#reply-(\d+)$/.exec(window.location.hash || "");
  return match ? Number(match[1]) : null;
}

function relativeWithQuery(path, params) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "" && !(key === "pagina" && Number(value) === 1)) {
      query.set(key, String(value));
    }
  });
  const text = query.toString();
  return text ? `${path}?${text}` : path;
}

function withQuery(path, params) {
  return mainPath(relativeWithQuery(path, params));
}

function sectionHref(slug) {
  return mainPath(`/discutii/sectiune/${encodeURIComponent(slug)}`);
}

function threadHref(slug) {
  return mainPath(`/discutii/${slug}`);
}

function forumCreateHref(section) {
  const query = section ? `?section=${encodeURIComponent(section)}` : "";
  return mainPath(`/discutii/nou${query}`);
}

function initialForumSection() {
  if (typeof window === "undefined") return "";
  return new URLSearchParams(window.location.search).get("section") || "";
}

function ForumBreadcrumbs({ items }) {
  return (
    <nav className="forum-breadcrumbs" aria-label="Navigare forum">
      {items.map((item, index) => (
        <span key={`${item.label}-${index}`} className="forum-breadcrumb">
          {item.href ? <a href={item.href}>{item.label}</a> : <span aria-current="page">{item.label}</span>}
        </span>
      ))}
    </nav>
  );
}

function ForumBadges({ pinned, locked, unread, archived, staffOnly }) {
  if (!pinned && !locked && !unread && !archived && !staffOnly) return null;
  return (
    <span className="forum-badges">
      {pinned ? <span className="forum-badge forum-badge-pinned"><FaThumbtack aria-hidden="true" /> fixată</span> : null}
      {locked ? <span className="forum-badge forum-badge-locked"><FaLock aria-hidden="true" /> închisă</span> : null}
      {unread ? <span className="forum-badge forum-badge-new">nou</span> : null}
      {staffOnly ? <span className="forum-badge">doar echipa</span> : null}
      {archived ? <span className="forum-badge forum-badge-archived">arhivată</span> : null}
    </span>
  );
}

function LastPost({ lastPost, threadSlug }) {
  if (!lastPost?.created_at) return null;
  const href = lastPost.reply_id ? `${threadHref(threadSlug)}#reply-${lastPost.reply_id}` : threadHref(threadSlug);
  return (
    <span className="forum-last-post">
      {lastPost.author?.username ? <>de <AuthorLink user={lastPost.author} /> · </> : null}
      <a href={href}>{formatDateTime(lastPost.created_at)}</a>
    </span>
  );
}

function ForumPager({ page, pages, hrefForPage }) {
  if (!pages || pages <= 1) return null;
  const numbers = [];
  for (let number = 1; number <= pages; number += 1) {
    if (number === 1 || number === pages || Math.abs(number - page) <= 2) numbers.push(number);
    else if (numbers[numbers.length - 1] !== "…") numbers.push("…");
  }
  return (
    <nav className="forum-pager" aria-label="Pagini">
      {page > 1 ? <a className="forum-pager-link" href={hrefForPage(page - 1)} rel="prev">‹ Înapoi</a> : null}
      {numbers.map((number, index) => (
        number === "…" ? (
          <span key={`gap-${index}`} className="forum-pager-gap">…</span>
        ) : (
          <a key={number} className={`forum-pager-link ${number === page ? "active" : ""}`.trim()} href={hrefForPage(number)} aria-current={number === page ? "page" : undefined}>
            {number}
          </a>
        )
      ))}
      {page < pages ? <a className="forum-pager-link" href={hrefForPage(page + 1)} rel="next">Înainte ›</a> : null}
    </nav>
  );
}

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

function ForumMessage({ item, isThread = false, user, authLoaded = true, onReport, reportBusy = false, permalink = "", moderatorAction = null, anchorId }) {
  const isModerating = MODERATING_STATUSES.has(item.moderation_status);
  const canReport = item.moderation_status === "approved";
  const elementId = anchorId === undefined ? (isThread ? undefined : `reply-${item.id}`) : anchorId;
  return (
    <article className={`${isThread ? "forum-post" : "forum-reply"} ${item.is_pinned && !isThread ? "is-pinned" : ""} ${isModerating ? "has-moderation-overlay" : ""}`.replace(/\s+/g, " ").trim()} id={elementId}>
      <ForumAuthorPanel author={item.author} />
      <div className={`forum-message-content ${canReport ? "has-report-action" : ""}`.trim()}>
        <div className="piece-card-meta forum-message-meta">
          <span>{formatDateTime(item.created_at)}</span>
          {!isThread && item.is_pinned ? <span className="forum-badge forum-badge-pinned"><FaThumbtack aria-hidden="true" /> fixat</span> : null}
          {!isThread && item.number ? (
            <a className="forum-reply-number" href={permalink || `#reply-${item.id}`} title="Legătură către răspuns">#{item.number}</a>
          ) : null}
          {moderatorAction}
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

function ForumThreadRow({ thread, showSection = false }) {
  const isModerating = MODERATING_STATUSES.has(thread.moderation_status);
  return (
    <article className={`forum-thread-row ${thread.is_pinned ? "is-pinned" : ""} ${isModerating ? "has-moderation-overlay" : ""}`.replace(/\s+/g, " ").trim()}>
      <div className="forum-thread-main">
        {showSection ? (
          <a className="forum-thread-section" href={sectionHref(thread.section)}>{thread.section_label || forumSectionLabel(thread.section)}</a>
        ) : null}
        <h2 className="forum-thread-title">
          <a className="post-title-link" href={threadHref(thread.slug)}>{thread.title}</a>
          <ForumBadges pinned={thread.is_pinned} locked={thread.is_locked} unread={thread.has_new_replies} />
        </h2>
        <div className="piece-card-meta">
          {thread.author?.username ? <span>pornită de <AuthorLink user={thread.author} /></span> : null}
          <span>{formatDateTime(thread.created_at)}</span>
        </div>
      </div>
      <dl className="forum-thread-stats">
        <div><dt>răspunsuri</dt><dd>{formatNumber(thread.reply_count)}</dd></div>
        <div><dt>vizualizări</dt><dd>{formatNumber(thread.view_count)}</dd></div>
      </dl>
      <div className="forum-thread-last">
        <span className="forum-last-label">ultima postare</span>
        <LastPost lastPost={thread.last_post} threadSlug={thread.slug} />
      </div>
      {isModerating ? (
        <ModerationOverlay className="forum-card-moderation-overlay">{TEXT_MODERATION_MESSAGE}</ModerationOverlay>
      ) : null}
    </article>
  );
}

function NewThreadButton({ user, authLoaded, section, canPost = true }) {
  const { openAuthModal } = useAuthModal();
  const createHref = forumCreateHref(section);
  if (user && !canPost) return null;
  return user ? (
    <a className="cal-btn primary" href={createHref}>Discuție nouă</a>
  ) : (
    <button className="cal-btn primary" type="button" disabled={!authLoaded} onClick={() => openAuthModal?.({ returnTo: createHref })}>
      Discuție nouă
    </button>
  );
}

function ForumSearchForm({ action, defaultValue = "", placeholder = "Caută în discuții" }) {
  return (
    <form className="forum-search" action={action} method="get" role="search">
      <input className="cal-input" type="search" name="q" defaultValue={defaultValue} placeholder={placeholder} aria-label={placeholder} />
      <button className="cal-btn" type="submit">Caută</button>
    </form>
  );
}

function SectionsSideNav({ sections, activeSlug }) {
  return (
    <aside className="side-col">
      <div className="side-kicker">secțiuni</div>
      <div className="actions-group">
        <ActionRow number="00" label="Toate secțiunile" active={!activeSlug} onClick={() => { window.location.href = mainPath("/discutii"); }} />
        {(sections || []).map((item, index) => (
          <ActionRow
            key={item.key}
            number={String(index + 1).padStart(2, "0")}
            label={item.label}
            className={item.featured ? "forum-section-featured" : ""}
            active={activeSlug === item.key}
            onClick={() => { window.location.href = sectionHref(item.key); }}
          />
        ))}
      </div>
    </aside>
  );
}

function ForumIndexView({ user, authLoaded }) {
  const q = queryParam("q").trim();
  const page = queryPage();
  const sectionsState = useAsync(() => fetchForumSections(), [user?.id]);
  const feedState = useAsync(
    () => fetchForumThreads({ q: q || undefined, page, perPage: q ? 25 : 10 }),
    [q, page, user?.id]
  );
  const sections = sectionsState.data?.sections || [];
  const data = feedState.data;

  return (
    <PageShell
      kicker="discuții"
      title="Discuții"
      sub="Forumul Călimarei: întrebări, ateliere și conversații între autori."
      className="forum-page"
      titleAction={<NewThreadButton user={user} authLoaded={authLoaded} section="" />}
      side={<SectionsSideNav sections={sections} activeSlug="" />}
    >
      <ForumSearchForm action={mainPath("/discutii")} defaultValue={q} />
      {q ? null : (
        <section className="forum-section-list" aria-label="Secțiuni">
          {sectionsState.loading ? <StatusPanel title="Se încarcă" /> : null}
          {sectionsState.error ? <StatusPanel title="Nu am putut încărca secțiunile">{sectionsState.error}</StatusPanel> : null}
          {sections.map((section) => (
            <article className={`forum-section-row ${section.featured ? "is-featured" : ""} ${section.is_archived ? "is-archived" : ""}`.replace(/\s+/g, " ").trim()} key={section.key}>
              <div className="forum-section-main">
                <h2 className="forum-section-title">
                  <a href={sectionHref(section.key)}>{section.label}</a>
                  <ForumBadges archived={section.is_archived} staffOnly={section.staff_only} />
                </h2>
                {section.description ? <p className="forum-section-description">{section.description}</p> : null}
              </div>
              <dl className="forum-thread-stats">
                <div><dt>discuții</dt><dd>{formatNumber(section.thread_count)}</dd></div>
                <div><dt>răspunsuri</dt><dd>{formatNumber(section.reply_count)}</dd></div>
              </dl>
              <div className="forum-thread-last">
                {section.last_thread ? (
                  <>
                    <a className="forum-last-thread" href={threadHref(section.last_thread.slug)}>{section.last_thread.title}</a>
                    <LastPost lastPost={section.last_thread.last_post} threadSlug={section.last_thread.slug} />
                  </>
                ) : <span className="forum-last-label">nicio discuție încă</span>}
              </div>
            </article>
          ))}
        </section>
      )}
      <section className="forum-thread-list" aria-label={q ? "Rezultate" : "Activitate recentă"}>
        <div className="piece-card-kicker">{q ? `rezultate pentru „${q}”` : "activitate recentă"}</div>
        {feedState.loading ? <StatusPanel title="Se încarcă" /> : null}
        {feedState.error ? <StatusPanel title="Nu am putut încărca discuțiile">{feedState.error}</StatusPanel> : null}
        {data?.threads?.length ? (
          data.threads.filter((thread) => thread.moderation_status !== "rejected").map((thread) => (
            <ForumThreadRow thread={thread} key={thread.id} showSection />
          ))
        ) : !feedState.loading && !feedState.error ? <p className="auth-sub">{q ? "Nicio discuție nu se potrivește căutării." : "Nu există discuții încă."}</p> : null}
        {q ? <ForumPager page={data?.page || 1} pages={data?.pages || 1} hrefForPage={(number) => withQuery("/discutii", { q, pagina: number })} /> : null}
      </section>
    </PageShell>
  );
}

function ForumSectionView({ user, authLoaded, slug }) {
  const q = queryParam("q").trim();
  const sort = THREAD_SORTS.some((item) => item.key === queryParam("ordine")) ? queryParam("ordine") : "activity";
  const page = queryPage();
  const section = slug;
  const sectionsState = useAsync(() => fetchForumSections(), [user?.id]);
  const { data, error, loading } = useAsync(
    () => fetchForumThreads({ section, q: q || undefined, sort, page }),
    [section, q, sort, page, user?.id]
  );
  const sectionInfo = data?.section;
  const basePath = `/discutii/sectiune/${encodeURIComponent(slug)}`;

  const changeSort = (event) => {
    window.location.href = withQuery(basePath, { q, ordine: event.target.value === "activity" ? "" : event.target.value });
  };

  return (
    <PageShell
      kicker="discuții"
      title={sectionInfo?.label ?? "Discuții"}
      sub={sectionInfo?.description || ""}
      className="forum-page"
      titleAction={sectionInfo ? <NewThreadButton user={user} authLoaded={authLoaded} section={section} canPost={sectionInfo.can_post} /> : null}
      side={<SectionsSideNav sections={sectionsState.data?.sections} activeSlug={slug} />}
    >
      <ForumBreadcrumbs items={[{ label: "Discuții", href: mainPath("/discutii") }, { label: sectionInfo?.label ?? slug }]} />
      {sectionInfo ? <ForumBadges archived={sectionInfo.is_archived} staffOnly={sectionInfo.staff_only} /> : null}
      <div className="forum-list-tools">
        <ForumSearchForm action={mainPath(basePath)} defaultValue={q} placeholder="Caută în secțiune" />
        <label className="forum-sort">
          <span>Ordonează</span>
          <select className="cal-input" value={sort} onChange={changeSort}>
            {THREAD_SORTS.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
          </select>
        </label>
      </div>
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca secțiunea">{error}</StatusPanel> : null}
      {data?.pinned?.length ? (
        <section className="forum-thread-list forum-pinned-list" aria-label="Discuții fixate">
          <div className="piece-card-kicker">fixate</div>
          {data.pinned.filter((thread) => thread.moderation_status !== "rejected").map((thread) => (
            <ForumThreadRow thread={thread} key={thread.id} />
          ))}
        </section>
      ) : null}
      {data ? (
        <section className="forum-thread-list" aria-label="Discuții">
          {data.pinned?.length ? <div className="piece-card-kicker">discuții</div> : null}
          {data.threads?.length ? (
            data.threads.filter((thread) => thread.moderation_status !== "rejected").map((thread) => (
              <ForumThreadRow thread={thread} key={thread.id} />
            ))
          ) : <p className="auth-sub">{q ? "Nicio discuție nu se potrivește căutării." : "Nu există discuții aici încă."}</p>}
          <ForumPager page={data.page} pages={data.pages} hrefForPage={(number) => withQuery(basePath, { q, ordine: sort === "activity" ? "" : sort, pagina: number })} />
        </section>
      ) : null}
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
  const sectionsState = useAsync(() => (user ? fetchForumSections() : Promise.resolve({ sections: [] })), [user?.id]);
  const postableSections = (sectionsState.data?.sections || []).filter((item) => item.can_post);
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

  useEffect(() => {
    // Keep the requested section when it accepts new threads; otherwise fall back to the first one that does.
    if (!postableSections.length) return;
    if (!postableSections.some((item) => item.key === section)) {
      const fallback = postableSections.find((item) => item.key === "general") || postableSections[0];
      setSection(fallback.key);
    }
  }, [sectionsState.data]);

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
      window.location.href = threadHref(thread.slug);
    } catch (requestError) {
      failDiacriticsProgress();
      setStatus(requestError.message || "Nu am putut publica discuția.");
      setSubmitting(false);
    }
  };

  return (
    <PageShell kicker="discuții" title="Discuție nouă" sub="Deschide o discuție în forum." className="forum-page">
      <DiacriticsProgressOverlay {...diacriticsProgress} />
      <ForumBreadcrumbs items={[{ label: "Discuții", href: mainPath("/discutii") }, { label: "Discuție nouă" }]} />
      {sectionsState.error ? <div className="inline-error">{sectionsState.error}</div> : null}
      <form className="form-stack" onSubmit={submit}>
        <label className="auth-field" htmlFor="forum-section">Secțiune</label>
        <select id="forum-section" className="cal-input" value={section} onChange={(event) => setSection(event.target.value)} disabled={sectionsState.loading}>
          {postableSections.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
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
        <button className="cal-btn primary" type="submit" disabled={submitting || !section}>
          {diacriticsSubmitLabel({
            submitting,
            reviewing: Boolean(diacriticsReview),
            enabled: Boolean(user && autoDiacritics),
            submitLabel: "Publică thread"
          })}
        </button>
        {user && autoDiacritics && !diacriticsReview ? (
          <button className="cal-btn" type="button" onClick={() => submit(null, { skipDiacritics: true })} disabled={submitting || !section}>
            Publică fără Diacritice
          </button>
        ) : null}
      </form>
    </PageShell>
  );
}

function ThreadModeratorTools({ data, sections, busy, onAction }) {
  const [moveTarget, setMoveTarget] = useState("");
  const targets = (sections || []).filter((item) => item.key !== data.section);
  return (
    <div className="forum-mod-tools" role="group" aria-label="Unelte de moderare">
      <span className="forum-mod-label">moderare</span>
      <button className="cal-btn" type="button" disabled={busy} onClick={() => onAction(data.is_pinned ? "unpin" : "pin")}>
        {data.is_pinned ? "Desprinde" : "Fixează"}
      </button>
      <button className="cal-btn" type="button" disabled={busy} onClick={() => onAction(data.is_locked ? "unlock" : "lock")}>
        {data.is_locked ? "Redeschide" : "Închide"}
      </button>
      <select className="cal-input" value={moveTarget} onChange={(event) => setMoveTarget(event.target.value)} aria-label="Mută în secțiunea">
        <option value="">Mută în…</option>
        {targets.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
      </select>
      <button className="cal-btn" type="button" disabled={busy || !moveTarget} onClick={() => onAction("move", moveTarget)}>Mută</button>
    </div>
  );
}

function ForumThreadDetailView({ user, authLoaded, slug }) {
  const [reply, setReply] = useState("");
  const [status, setStatus] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [page, setPage] = useState(queryPage);
  const [targetReply, setTargetReply] = useState(hashReplyId);
  const [replyAutoDiacritics, setReplyAutoDiacritics] = useState(false);
  const [replyReview, setReplyReview] = useState(null);
  const [reportModal, setReportModal] = useState(null);
  const [reportDetails, setReportDetails] = useState("");
  const [reportEvidenceUrl, setReportEvidenceUrl] = useState("");
  const [reportBusy, setReportBusy] = useState("");
  const [reportStatus, setReportStatus] = useState("");
  const [modBusy, setModBusy] = useState(false);
  const [modStatus, setModStatus] = useState("");
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
  // Jumping to a reply lets the server pick its page; otherwise load the requested page.
  const fetchKey = targetReply ? `reply-${targetReply}` : `page-${page}`;
  const { data, error, loading } = useAsync(
    () => fetchForumThread(slug, targetReply ? { reply: targetReply } : { page }),
    [slug, fetchKey, refreshKey]
  );
  const sectionsState = useAsync(
    () => (data?.can_moderate ? fetchForumSections() : Promise.resolve(null)),
    [Boolean(data?.can_moderate)]
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

  useEffect(() => {
    // After loading a specific reply, scroll to it and keep the URL in sync with the page it landed on.
    if (!data) return;
    if (data.reply_page && data.reply_page !== page) setPage(data.reply_page);
    if (typeof window !== "undefined") {
      const url = relativeWithQuery(`/discutii/${slug}`, { pagina: data.reply_page }) + (targetReply ? `#reply-${targetReply}` : "");
      try {
        window.history.replaceState(null, "", url);
      } catch {
        // Keeping the address bar in sync is a nicety; never break the page over it.
      }
      if (targetReply) {
        const element = document.getElementById(`reply-${targetReply}`);
        element?.scrollIntoView({ block: "center" });
      }
    }
  }, [data]);

  const goToPage = (number) => {
    setTargetReply(null);
    setPage(number);
    if (typeof window !== "undefined") window.scrollTo({ top: 0 });
  };

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

  const runThreadAction = async (action, section) => {
    if (!data || modBusy) return;
    setModBusy(true);
    setModStatus("");
    try {
      await updateForumThreadState(data.id, action, section);
      setRefreshKey((key) => key + 1);
    } catch (requestError) {
      setModStatus(requestError.message || "Acțiunea nu a reușit.");
    } finally {
      setModBusy(false);
    }
  };

  const toggleReplyPin = async (item) => {
    if (modBusy) return;
    setModBusy(true);
    setModStatus("");
    try {
      await updateForumReplyState(item.id, item.is_pinned ? "unpin" : "pin");
      setRefreshKey((key) => key + 1);
    } catch (requestError) {
      setModStatus(requestError.message || "Acțiunea nu a reușit.");
    } finally {
      setModBusy(false);
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
      setTargetReply(created.id);
      setRefreshKey((key) => key + 1);
    } catch (requestError) {
      failDiacriticsProgress();
      setStatus(requestError.message || "Nu am putut publica răspunsul.");
    } finally {
      setSubmitting(false);
    }
  };

  const replyPermalink = (item) => `${withQuery(`/discutii/${slug}`, {})}#reply-${item.id}`;
  const replyPinAction = (item) => (data?.can_moderate && item.moderation_status === "approved" ? (
    <button className="forum-inline-action" type="button" disabled={modBusy} onClick={() => toggleReplyPin(item)}>
      {item.is_pinned ? "desprinde" : "fixează"}
    </button>
  ) : null);
  const sectionLabel = data?.section_info?.label ?? data?.section_label ?? forumSectionLabel(data?.section);

  return (
    <PageShell
      kicker={data ? sectionLabel : "discuții"}
      title={data?.title ?? "Discuții"}
      sub={data?.author?.username ? <>Pornit de <AuthorLink user={data.author} /></> : ""}
      className="forum-page"
    >
      <DiacriticsProgressOverlay {...diacriticsProgress} />
      {data ? (
        <ForumBreadcrumbs items={[
          { label: "Discuții", href: mainPath("/discutii") },
          { label: sectionLabel, href: sectionHref(data.section) },
          { label: data.title }
        ]} />
      ) : null}
      {loading && !data ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca discuția">{error}</StatusPanel> : null}
      {data ? (
        <div className="detail-stack">
          <div className="forum-thread-head">
            <ForumBadges pinned={data.is_pinned} locked={data.is_locked} />
            <span className="piece-card-meta">
              <span>{formatNumber(data.reply_total)} răspunsuri</span>
              <span>{formatNumber(data.view_count)} vizualizări</span>
            </span>
          </div>
          {data.can_moderate ? (
            <ThreadModeratorTools data={data} sections={sectionsState.data?.sections} busy={modBusy} onAction={runThreadAction} />
          ) : null}
          {modStatus ? <div className="inline-error">{modStatus}</div> : null}
          {reportStatus ? <div className="inline-status">{reportStatus}</div> : null}
          {data.reply_page === 1 ? (
            <ForumMessage item={data} isThread user={user} authLoaded={authLoaded} onReport={openReportModal} reportBusy={Boolean(reportBusy)} />
          ) : null}
          {data.pinned_replies?.length ? (
            <section className="forum-pinned-replies" aria-label="Răspunsuri fixate">
              <div className="piece-card-kicker">răspunsuri fixate</div>
              {data.pinned_replies.map((item) => (
                <ForumMessage
                  item={item}
                  key={`pinned-${item.id}`}
                  anchorId={null}
                  user={user}
                  authLoaded={authLoaded}
                  onReport={openReportModal}
                  reportBusy={Boolean(reportBusy)}
                  permalink={replyPermalink(item)}
                  moderatorAction={replyPinAction(item)}
                />
              ))}
            </section>
          ) : null}
          <section className="forum-replies" aria-label="Răspunsuri">
            <div className="piece-card-kicker">răspunsuri</div>
            {data.replies?.length ? (
              <div className="reply-list">
                {data.replies.filter((item) => item.moderation_status !== "rejected").map((item) => (
                  <ForumMessage
                    item={item}
                    key={item.id}
                    user={user}
                    authLoaded={authLoaded}
                    onReport={openReportModal}
                    reportBusy={Boolean(reportBusy)}
                    permalink={replyPermalink(item)}
                    moderatorAction={replyPinAction(item)}
                  />
                ))}
              </div>
            ) : <p className="auth-sub">Nu există răspunsuri încă.</p>}
            <ForumPagerButtons page={data.reply_page} pages={data.reply_pages} onPage={goToPage} />
          </section>
          {data.is_locked && !data.can_moderate ? (
            <StatusPanel title="Discuție închisă">Nu mai pot fi adăugate răspunsuri.</StatusPanel>
          ) : data.section_info?.is_archived && !data.can_moderate ? (
            <StatusPanel title="Secțiune arhivată">Discuțiile din această secțiune nu mai primesc răspunsuri.</StatusPanel>
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

function ForumPagerButtons({ page, pages, onPage }) {
  if (!pages || pages <= 1) return null;
  const numbers = [];
  for (let number = 1; number <= pages; number += 1) {
    if (number === 1 || number === pages || Math.abs(number - page) <= 2) numbers.push(number);
    else if (numbers[numbers.length - 1] !== "…") numbers.push("…");
  }
  return (
    <nav className="forum-pager" aria-label="Pagini de răspunsuri">
      {page > 1 ? <button className="forum-pager-link" type="button" onClick={() => onPage(page - 1)}>‹ Înapoi</button> : null}
      {numbers.map((number, index) => (
        number === "…" ? (
          <span key={`gap-${index}`} className="forum-pager-gap">…</span>
        ) : (
          <button key={number} className={`forum-pager-link ${number === page ? "active" : ""}`.trim()} type="button" aria-current={number === page ? "page" : undefined} onClick={() => onPage(number)}>
            {number}
          </button>
        )
      ))}
      {page < pages ? <button className="forum-pager-link" type="button" onClick={() => onPage(page + 1)}>Înainte ›</button> : null}
    </nav>
  );
}

export default function ForumRoute({ route, user, authLoaded }) {
  if (route.name === "forumCreate") return <ForumThreadCreateView user={user} />;
  if (route.name === "forumThread") return <ForumThreadDetailView user={user} authLoaded={authLoaded} slug={route.slug} />;
  if (route.name === "forumSection") return <ForumSectionView user={user} authLoaded={authLoaded} slug={route.slug} />;
  // Old links used /discutii?section=<slug>; send them to the section page.
  const legacySection = queryParam("section");
  if (legacySection) return <ForumSectionView user={user} authLoaded={authLoaded} slug={legacySection} />;
  return <ForumIndexView user={user} authLoaded={authLoaded} />;
}
