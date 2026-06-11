import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPost, createPostDraft, fetchOwnedPostForEdit, fetchPostDraft, fetchPostDrafts, updatePost, updatePostDraft } from "../api/posts.js";
import { addDiacritics, formatPostWithAi } from "../api/writing.js";
import { EXPLANATORY_NOTE_CHARACTER_LIMIT, POST_CATEGORIES, POST_CONTENT_LIMITS, POST_DRAFT_AUTOSAVE_MS, SHORT_STORY_CHARACTER_LIMIT, TITLE_CHARACTER_LIMIT } from "../app/constants.js";
import { DiacriticsControl, DiacriticsProgressOverlay, DiacriticsReviewPanel, diacriticsSubmitLabel, useDiacriticsProgress, useDiacriticsQuota } from "../app/diacritics.jsx";
import { RichTextEditor } from "../app/editor.jsx";
import { categoryLabel, draftFingerprint, draftHasContent, formatDateTime, formatNumber, htmlToText } from "../app/format.js";
import { useAsync } from "../app/hooks.js";
import { AuthRequired, PageShell } from "../app/layout.jsx";
import { authorPath, blogUrl } from "../app/paths.js";

function CreatePostView({ user }) {
  const draftParam = useMemo(() => {
    const raw = new URLSearchParams(window.location.search).get("draft");
    const parsed = Number(raw);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  }, []);
  const postParam = useMemo(() => {
    const raw = new URLSearchParams(window.location.search).get("post");
    const parsed = Number(raw);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  }, []);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [explanatoryNote, setExplanatoryNote] = useState("");
  const [category, setCategory] = useState("poezie");
  const [status, setStatus] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [directPublishing, setDirectPublishing] = useState(false);
  const [formattingWithAi, setFormattingWithAi] = useState(false);
  const [autoDiacritics, setAutoDiacritics] = useState(false);
  const [diacriticsReview, setDiacriticsReview] = useState(null);
  const [draftId, setDraftId] = useState(null);
  const [draftStatus, setDraftStatus] = useState("");
  const [draftError, setDraftError] = useState("");
  const [draftSaving, setDraftSaving] = useState(false);
  const [draftLoading, setDraftLoading] = useState(false);
  const [draftsRefreshKey, setDraftsRefreshKey] = useState(0);
  const contentLimit = POST_CONTENT_LIMITS[category] ?? SHORT_STORY_CHARACTER_LIMIT;
  const titleRef = useRef("");
  const contentRef = useRef("");
  const explanatoryNoteRef = useRef("");
  const categoryRef = useRef("poezie");
  const draftIdRef = useRef(null);
  const lastSavedFingerprintRef = useRef("");
  const savingDraftRef = useRef(false);
  const pendingDraftSaveRef = useRef(false);
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
  const draftListState = useAsync(
    () => (user && !postParam ? fetchPostDrafts() : Promise.resolve({ drafts: [] })),
    [user?.id, postParam, draftsRefreshKey]
  );

  useEffect(() => {
    titleRef.current = title;
  }, [title]);

  useEffect(() => {
    contentRef.current = content;
  }, [content]);

  useEffect(() => {
    explanatoryNoteRef.current = explanatoryNote;
  }, [explanatoryNote]);

  useEffect(() => {
    categoryRef.current = category;
  }, [category]);

  useEffect(() => {
    draftIdRef.current = draftId;
  }, [draftId]);

  useEffect(() => {
    setAutoDiacritics(false);
    setDiacriticsReview(null);
    setDraftStatus("");
    setDraftError("");
    if (postParam || !draftParam) {
      setDraftId(null);
      lastSavedFingerprintRef.current = "";
    }
  }, [user?.id, draftParam, postParam]);

  useEffect(() => {
    if (!user || !postParam) return undefined;
    let cancelled = false;
    setDraftLoading(true);
    setDraftError("");
    fetchOwnedPostForEdit(postParam)
      .then((post) => {
        if (cancelled) return;
        const nextTitle = post.title || "";
        const nextContent = post.content || "";
        const nextExplanatoryNote = post.explanatory_note || "";
        const nextCategory = post.category || "poezie";
        setDraftId(null);
        setTitle(nextTitle);
        setContent(nextContent);
        setExplanatoryNote(nextExplanatoryNote);
        setCategory(nextCategory);
        lastSavedFingerprintRef.current = draftFingerprint(`${nextCategory}:${nextTitle}`, nextContent, nextExplanatoryNote);
        setDraftStatus("Postare încărcată pentru editare.");
      })
      .catch((requestError) => {
        if (!cancelled) {
          setDraftError(requestError.message || "Nu am putut încărca postarea.");
        }
      })
      .finally(() => {
        if (!cancelled) setDraftLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user?.id, postParam]);

  useEffect(() => {
    if (!user || !draftParam || postParam) return undefined;
    let cancelled = false;
    setDraftLoading(true);
    setDraftError("");
    fetchPostDraft(draftParam)
      .then((draft) => {
        if (cancelled) return;
        const nextTitle = draft.title || "";
        const nextContent = draft.content || "";
        const nextExplanatoryNote = draft.explanatory_note || "";
        const nextCategory = draft.category || "poezie";
        setDraftId(draft.id);
        setTitle(nextTitle);
        setContent(nextContent);
        setExplanatoryNote(nextExplanatoryNote);
        setCategory(nextCategory);
        lastSavedFingerprintRef.current = draftFingerprint(`${nextCategory}:${nextTitle}`, nextContent, nextExplanatoryNote);
        setDraftStatus("Ciornă încărcată.");
      })
      .catch((requestError) => {
        if (!cancelled) {
          setDraftError(requestError.message || "Nu am putut încărca ciorna.");
        }
      })
      .finally(() => {
        if (!cancelled) setDraftLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user?.id, draftParam, postParam]);

  const saveDraft = useCallback(async (source = "manual") => {
    if (!user) return null;
    if (savingDraftRef.current) {
      pendingDraftSaveRef.current = true;
      return null;
    }

    savingDraftRef.current = true;
    setDraftSaving(true);
    setDraftError("");

    try {
      let savedDraft = null;
      do {
        pendingDraftSaveRef.current = false;
        const snapshot = {
          title: titleRef.current.trim(),
          content: contentRef.current || "",
          explanatory_note: explanatoryNoteRef.current.trim() || null,
          category: categoryRef.current || "poezie"
        };
        const fingerprint = draftFingerprint(`${snapshot.category}:${snapshot.title}`, snapshot.content, snapshot.explanatory_note);

        if (!draftHasContent(snapshot.title, snapshot.content)) {
          if (source === "manual") {
            setDraftError("Scrie un titlu sau un text înainte să salvezi ciorna.");
          }
          return null;
        }

        if (snapshot.title.length > TITLE_CHARACTER_LIMIT) {
          setDraftError(`Titlul poate avea cel mult ${formatNumber(TITLE_CHARACTER_LIMIT)} de caractere.`);
          return null;
        }
        if ((snapshot.explanatory_note || "").length > EXPLANATORY_NOTE_CHARACTER_LIMIT) {
          setDraftError(`Nota explicativă poate avea cel mult ${formatNumber(EXPLANATORY_NOTE_CHARACTER_LIMIT)} de caractere.`);
          return null;
        }

        const snapshotLimit = POST_CONTENT_LIMITS[snapshot.category] ?? SHORT_STORY_CHARACTER_LIMIT;
        const visibleContent = htmlToText(snapshot.content);
        if (visibleContent.length > snapshotLimit) {
          const label = snapshot.category === "poezie" ? "poezia" : "proza scurtă";
          setDraftError(`Pentru ${label}, textul poate avea cel mult ${formatNumber(snapshotLimit)} de caractere.`);
          return null;
        }

        if (fingerprint === lastSavedFingerprintRef.current) {
          if (source === "manual") setDraftStatus("Ciorna este deja salvată.");
          return savedDraft;
        }

        savedDraft = draftIdRef.current
          ? await updatePostDraft(draftIdRef.current, snapshot)
          : await createPostDraft(snapshot);

        draftIdRef.current = savedDraft.id;
        setDraftId(savedDraft.id);
        lastSavedFingerprintRef.current = draftFingerprint(`${savedDraft.category}:${savedDraft.title}`, savedDraft.content, savedDraft.explanatory_note);
        setDraftStatus(source === "auto" ? "Salvat automat." : "Ciornă salvată.");
        setDraftsRefreshKey((key) => key + 1);

        const currentFingerprint = draftFingerprint(
          `${categoryRef.current || "poezie"}:${titleRef.current.trim()}`,
          contentRef.current || "",
          explanatoryNoteRef.current
        );
        if (currentFingerprint !== lastSavedFingerprintRef.current) {
          pendingDraftSaveRef.current = true;
        }
      } while (pendingDraftSaveRef.current);

      return savedDraft;
    } catch (requestError) {
      setDraftError(requestError.message || "Nu am putut salva ciorna.");
      return null;
    } finally {
      savingDraftRef.current = false;
      setDraftSaving(false);
    }
  }, [user?.id]);

  useEffect(() => {
    if (!user || postParam) return undefined;
    const timer = window.setInterval(() => {
      if (!submitting) saveDraft("auto");
    }, POST_DRAFT_AUTOSAVE_MS);
    return () => window.clearInterval(timer);
  }, [user?.id, postParam, submitting, saveDraft]);

  if (!user) return <AuthRequired />;

  const otherDrafts = postParam ? [] : (draftListState.data?.drafts ?? []).filter((draft) => draft.id !== draftId);
  const canSaveDraft = !postParam && draftHasContent(title, content);
  const canPublishDirectly = Boolean(user && autoDiacritics && !diacriticsReview);

  const submitPost = async ({ skipDiacritics = false } = {}) => {
    if (submitting) return;
    setSubmitting(true);
    setDirectPublishing(skipDiacritics);
    setStatus("");
    const visibleContent = htmlToText(content);
    if (!title.trim() || !visibleContent) {
      setStatus("Titlul și textul sunt obligatorii.");
      setSubmitting(false);
      setDirectPublishing(false);
      return;
    }
    if (title.trim().length > TITLE_CHARACTER_LIMIT) {
      setStatus(`Titlul poate avea cel mult ${formatNumber(TITLE_CHARACTER_LIMIT)} de caractere.`);
      setSubmitting(false);
      setDirectPublishing(false);
      return;
    }
    const normalizedExplanatoryNote = explanatoryNote.trim();
    if (normalizedExplanatoryNote.length > EXPLANATORY_NOTE_CHARACTER_LIMIT) {
      setStatus(`Nota explicativă poate avea cel mult ${formatNumber(EXPLANATORY_NOTE_CHARACTER_LIMIT)} de caractere.`);
      setSubmitting(false);
      setDirectPublishing(false);
      return;
    }
    if (visibleContent.length > contentLimit) {
      const label = category === "poezie" ? "poezia" : "proza scurtă";
      setStatus(`Pentru ${label}, textul poate avea cel mult ${formatNumber(contentLimit)} de caractere.`);
      setSubmitting(false);
      setDirectPublishing(false);
      return;
    }
    try {
      if (!skipDiacritics && user && autoDiacritics && !diacriticsReview) {
        startDiacriticsProgress({ title, content });
        const converted = await addDiacritics({ kind: "post", title, content, category });
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
        setDirectPublishing(false);
        return;
      }
      const payload = { title, content, category, explanatory_note: normalizedExplanatoryNote || null };
      if (!postParam && draftIdRef.current) payload.draft_id = draftIdRef.current;
      const post = postParam ? await updatePost(postParam, payload) : await createPost(payload);
      lastSavedFingerprintRef.current = draftFingerprint(`${category}:${title}`, content, normalizedExplanatoryNote);
      window.location.href = `${blogUrl(user.username)}/${post.slug}`;
    } catch (requestError) {
      failDiacriticsProgress();
      setStatus(requestError.message || (postParam ? "Nu am putut salva postarea." : "Nu am putut publica textul."));
      setSubmitting(false);
      setDirectPublishing(false);
    }
  };

  const submit = async (event) => {
    event.preventDefault();
    await submitPost();
  };

  const formatContentWithAi = async () => {
    if (formattingWithAi || submitting) return;
    const visibleContent = htmlToText(content);
    if (!visibleContent) {
      setStatus("Scrie sau lipește un text înainte să cureți formatarea cu AI.");
      return;
    }

    setFormattingWithAi(true);
    setStatus("");
    setDraftError("");
    try {
      const result = await formatPostWithAi({ category, content });
      if (result.category === "poezie" || result.category === "proza_scurta") {
        setCategory(result.category);
      }
      setContent(result.content);
      setDiacriticsReview(null);
      setDraftStatus("Formatarea AI a fost aplicată. Verifică textul înainte să publici.");
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut curăța formatarea cu AI.");
    } finally {
      setFormattingWithAi(false);
    }
  };

  return (
    <PageShell
      kicker="scrie"
      title={postParam ? "Editează postarea" : "Text nou"}
      sub={postParam ? "Modificările retrimit textul la moderare." : "Publică un text în blogul tău."}
    >
      <DiacriticsProgressOverlay {...diacriticsProgress} />
      <form className="form-stack" onSubmit={submit}>
        <label className="auth-field" htmlFor="post-title">Titlu</label>
        <input id="post-title" className="cal-input" value={title} onChange={(event) => setTitle(event.target.value)} maxLength={TITLE_CHARACTER_LIMIT} required />
        <label className="auth-field" htmlFor="post-category">Categorie</label>
        <select
          id="post-category"
          className="cal-input"
          value={category}
          onChange={(event) => {
            setCategory(event.target.value);
            setDiacriticsReview(null);
          }}
        >
          {POST_CATEGORIES.map((item) => (
            <option key={item.key} value={item.key}>
              {item.label} - {formatNumber(item.limit)} caractere
            </option>
          ))}
        </select>
        <label className="auth-field" htmlFor="post-content">Text</label>
        <RichTextEditor
          id="post-content"
          className="tall"
          value={content}
          onChange={setContent}
          maxLength={contentLimit}
          enterMode="soft-break"
          pasteMode={category === "poezie" ? "poetry" : "prose"}
          showFormatCleanup
          formatCleanupLabel="Curăță formatarea cu AI"
          formatCleanupBusy={formattingWithAi}
          onFormatCleanup={formatContentWithAi}
        />
        <label className="auth-field" htmlFor="post-explanatory-note">Notă explicativă (opțional)</label>
        <textarea
          id="post-explanatory-note"
          className="cal-textarea explanatory-note-input"
          value={explanatoryNote}
          onChange={(event) => setExplanatoryNote(event.target.value)}
          maxLength={EXPLANATORY_NOTE_CHARACTER_LIMIT}
          rows={3}
          placeholder="Ce ar ajuta cititorul să știe despre text?"
        />
        <div className="field-counter">{formatNumber(explanatoryNote.length)}/{formatNumber(EXPLANATORY_NOTE_CHARACTER_LIMIT)}</div>
        {postParam ? (
          <span className="draft-save-status">{draftLoading ? "Se încarcă postarea..." : draftStatus}</span>
        ) : (
          <div className="draft-actions-row">
            <button className="cal-btn" type="button" onClick={() => saveDraft("manual")} disabled={submitting || draftSaving || !canSaveDraft}>
              {draftSaving ? "Se salvează..." : "Salvează ca ciornă"}
            </button>
            <span className="draft-save-status">{draftLoading ? "Se încarcă ciorna..." : draftStatus}</span>
          </div>
        )}
        {draftError ? <div className="inline-error">{draftError}</div> : null}
        {draftListState.error ? <div className="inline-error">{draftListState.error}</div> : null}
        {otherDrafts.length ? (
          <section className="draft-resume-list" aria-label="Alte ciorne">
            <div className="piece-card-kicker">alte ciorne</div>
            <div className="draft-chip-row">
              {otherDrafts.slice(0, 5).map((draft) => (
                <a className="draft-chip" key={draft.id} href={`${authorPath(user, "/scrie")}?draft=${encodeURIComponent(draft.id)}`}>
                  <span>{draft.title?.trim() || "Ciornă fără titlu"}</span>
                  <small>{categoryLabel(draft.category)}{draft.updated_at ? ` · ${formatDateTime(draft.updated_at)}` : ""}</small>
                </a>
              ))}
            </div>
          </section>
        ) : null}
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
        <div className="button-row">
          <button className="cal-btn primary" type="submit" disabled={submitting}>
            {diacriticsSubmitLabel({
              submitting,
              reviewing: Boolean(diacriticsReview),
              enabled: Boolean(user && autoDiacritics && !directPublishing),
              submitLabel: postParam ? "Salvează" : "Publică"
            })}
          </button>
          {canPublishDirectly ? (
            <button className="cal-btn" type="button" onClick={() => submitPost({ skipDiacritics: true })} disabled={submitting}>
              {directPublishing ? (postParam ? "Se salvează..." : "Se publică...") : (postParam ? "Salvează fără Diacritice" : "Publică fără Diacritice")}
            </button>
          ) : null}
        </div>
      </form>
    </PageShell>
  );
}

export default function CreateRoute({ user }) {
  return <CreatePostView user={user} />;
}
