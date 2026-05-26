import { useEffect, useRef, useState } from "react";
import { FiArrowDown, FiArrowUp, FiChevronLeft, FiChevronRight, FiEdit3, FiEye, FiHeadphones, FiPlus, FiStar, FiTrash2, FiUpload, FiX } from "react-icons/fi";
import { audioDownloadUrl, fetchAudioConversionQuota, requestTtsConversions, uploadPostAudioRecording } from "../api/audio.js";
import { createSeries, deleteSeries, fetchManagedSeries, fetchMySeries, addPostToSeries, removePostFromSeries, reorderSeriesPosts, updateSeries } from "../api/series.js";
import { deletePost, deletePostDraft, fetchArchive, fetchPostDrafts } from "../api/posts.js";
import { fetchPromotions, promotePost, unpromotePost } from "../api/users.js";
import { fetchDiacriticsQuota } from "../api/writing.js";
import { MODERATING_STATUSES, TEXT_MODERATION_MESSAGE, TITLE_CHARACTER_LIMIT } from "../app/constants.js";
import { CompactAudioPlayer, ModerationOverlay, postHref } from "../app/content.jsx";
import { audioStatusLabel, categoryLabel, formatDateTime, formatNumber, htmlToText, usernameHandle } from "../app/format.js";
import { useAsync } from "../app/hooks.js";
import { AuthRequired, PageShell } from "../app/layout.jsx";
import { authorPath, mainPath } from "../app/paths.js";

const DASHBOARD_PAGE_SIZE = 25;
const AUTHOR_AUDIO_ACCEPT = "audio/mpeg,audio/mp3,audio/wav,audio/x-wav,audio/ogg,audio/webm,audio/mp4,audio/x-m4a";

function dashboardOffset(page) {
  return (Math.max(1, page) - 1) * DASHBOARD_PAGE_SIZE;
}

function pageCountFor(total) {
  return Math.max(1, Math.ceil(Number(total || 0) / DASHBOARD_PAGE_SIZE));
}

function DashboardPager({ page, total, onPageChange }) {
  const pageCount = pageCountFor(total);
  if (pageCount <= 1) return null;

  return (
    <nav className="dashboard-pager" aria-label="Paginare">
      <button className="icon-btn" type="button" aria-label="Pagina anterioară" onClick={() => onPageChange(page - 1)} disabled={page <= 1}>
        <FiChevronLeft aria-hidden="true" />
      </button>
      <span>Pagina {formatNumber(page)} din {formatNumber(pageCount)}</span>
      <button className="icon-btn" type="button" aria-label="Pagina următoare" onClick={() => onPageChange(page + 1)} disabled={page >= pageCount}>
        <FiChevronRight aria-hidden="true" />
      </button>
    </nav>
  );
}

function DashboardView({ user }) {
  const [activeTab, setActiveTab] = useState("posts");
  const [postPage, setPostPage] = useState(1);
  const [draftPage, setDraftPage] = useState(1);
  const [postRefreshKey, setPostRefreshKey] = useState(0);
  const [draftRefreshKey, setDraftRefreshKey] = useState(0);
  const [status, setStatus] = useState(null);
  const [audioBusyId, setAudioBusyId] = useState(null);
  const [authorAudioBusyId, setAuthorAudioBusyId] = useState(null);
  const [deletingPostId, setDeletingPostId] = useState(null);
  const [draftBusyId, setDraftBusyId] = useState(null);
  const [promotionState, setPromotionState] = useState(null);
  const [promotionBusyId, setPromotionBusyId] = useState(null);

  const { data, error, loading } = useAsync(
    () => (user ? fetchArchive({ limit: DASHBOARD_PAGE_SIZE, offset: dashboardOffset(postPage) }) : Promise.resolve({ posts: [], total: 0 })),
    [user?.id, postPage, postRefreshKey]
  );
  const draftState = useAsync(
    () => (user ? fetchPostDrafts({ limit: DASHBOARD_PAGE_SIZE, offset: dashboardOffset(draftPage) }) : Promise.resolve({ drafts: [], total: 0 })),
    [user?.id, draftPage, draftRefreshKey]
  );
  const quotaState = useAsync(
    () => (user ? fetchAudioConversionQuota() : Promise.resolve(null)),
    [user?.id, postRefreshKey]
  );
  const diacriticsQuotaState = useAsync(
    () => (user ? fetchDiacriticsQuota() : Promise.resolve(null)),
    [user?.id, user?.premium_tier, user?.premium_until]
  );
  const promotionsState = useAsync(
    () => (user ? fetchPromotions() : Promise.resolve(null)),
    [user?.id, postRefreshKey]
  );

  const posts = (data?.posts ?? []).filter((post) => post.moderation_status !== "rejected");
  const drafts = draftState.data?.drafts ?? [];
  const postTotal = data?.total ?? posts.length;
  const draftTotal = draftState.data?.total ?? drafts.length;
  const quota = quotaState.data;
  const diacriticsQuota = diacriticsQuotaState.data;
  const canRequestAudio = Boolean(quota?.can_request);
  const remaining = Number(quota?.remaining ?? 0);
  const promotionSnapshot = promotionState || promotionsState.data;
  const promotionLimits = promotionSnapshot?.limits || { own_posts: 2 };
  const promotedOwnPosts = promotionSnapshot?.own_posts || [];
  const promotedOwnPostIds = new Set(promotedOwnPosts.map((post) => post.id));

  useEffect(() => {
    const maxPage = pageCountFor(postTotal);
    if (postPage > maxPage) setPostPage(maxPage);
  }, [postPage, postTotal]);

  useEffect(() => {
    const maxPage = pageCountFor(draftTotal);
    if (draftPage > maxPage) setDraftPage(maxPage);
  }, [draftPage, draftTotal]);

  useEffect(() => {
    if (promotionsState.data) setPromotionState(promotionsState.data);
  }, [promotionsState.data]);

  useEffect(() => {
    setPromotionState(null);
  }, [user?.id]);

  if (!user) return <AuthRequired />;

  const togglePostPromotion = async (post) => {
    if (promotionBusyId || deletingPostId === post.id) return;
    if (post.moderation_status !== "approved") {
      setStatus({ kind: "error", text: "Poți promova doar texte aprobate." });
      return;
    }
    const promoted = promotedOwnPostIds.has(post.id);
    if (!promoted && promotedOwnPosts.length >= Number(promotionLimits.own_posts || 2)) {
      setStatus({ kind: "error", text: `Poți promova cel mult ${formatNumber(promotionLimits.own_posts || 2)} texte proprii.` });
      return;
    }
    setPromotionBusyId(post.id);
    setStatus(null);
    try {
      const response = promoted ? await unpromotePost(post.id) : await promotePost(post.id);
      setPromotionState(response.promotions);
      setStatus({ kind: "info", text: promoted ? "Textul a fost scos din promovări." : "Textul a fost adăugat în promovări." });
    } catch (requestError) {
      setStatus({ kind: "error", text: requestError.message || "Nu am putut actualiza promovarea." });
    } finally {
      setPromotionBusyId(null);
    }
  };

  const convertPostToAudio = async (post) => {
    const characterCount = Number(post.audio_tts_character_count ?? 0);
    if (audioBusyId || !canRequestAudio || !post.audio_can_request || characterCount > remaining) return;
    setAudioBusyId(post.id);
    setStatus(null);
    try {
      const response = await requestTtsConversions([post.id]);
      setStatus({
        kind: "info",
        text: response.queued?.length
          ? `„${post.title}” a fost trimisă la generare audio.`
          : "Postarea avea deja audio sau era deja în coadă."
      });
      setPostRefreshKey((key) => key + 1);
    } catch (requestError) {
      setStatus({ kind: "error", text: requestError.message || "Nu am putut porni generarea audio." });
    } finally {
      setAudioBusyId(null);
    }
  };

  const removePost = async (post) => {
    if (deletingPostId) return;
    if (!window.confirm(`Ștergi definitiv "${post.title}"?`)) return;
    setDeletingPostId(post.id);
    setStatus(null);
    try {
      await deletePost(post.id);
      setStatus({ kind: "info", text: "Postarea a fost ștearsă." });
      if (posts.length === 1 && postPage > 1) {
        setPostPage((page) => page - 1);
      } else {
        setPostRefreshKey((key) => key + 1);
      }
    } catch (requestError) {
      setStatus({ kind: "error", text: requestError.message || "Nu am putut șterge postarea." });
    } finally {
      setDeletingPostId(null);
    }
  };

  const uploadAuthorAudio = async (post, file) => {
    if (!file || authorAudioBusyId || !post.author_audio_can_upload) return;
    setAuthorAudioBusyId(post.id);
    setStatus(null);
    try {
      await uploadPostAudioRecording(post.id, file);
      setStatus({ kind: "info", text: `Lectura pentru „${post.title}” a fost încărcată și intră la verificare.` });
      setPostRefreshKey((key) => key + 1);
    } catch (requestError) {
      setStatus({ kind: "error", text: requestError.message || "Nu am putut încărca înregistrarea audio." });
    } finally {
      setAuthorAudioBusyId(null);
    }
  };

  const discardDraft = async (draft) => {
    if (draftBusyId) return;
    setDraftBusyId(draft.id);
    setStatus(null);
    try {
      await deletePostDraft(draft.id);
      setStatus({ kind: "info", text: "Ciorna a fost ștearsă." });
      if (drafts.length === 1 && draftPage > 1) {
        setDraftPage((page) => page - 1);
      } else {
        setDraftRefreshKey((key) => key + 1);
      }
    } catch (requestError) {
      setStatus({ kind: "error", text: requestError.message || "Nu am putut șterge ciorna." });
    } finally {
      setDraftBusyId(null);
    }
  };

  return (
    <PageShell kicker="panou" title="Textele tale" sub={`Conectat ca ${usernameHandle(user.username)}.`}>
      <div className="dashboard-action-row">
        <a className="dashboard-write-btn" href={authorPath(user, "/scrie")}>
          <FiPlus aria-hidden="true" />
          <span>Postare nouă</span>
        </a>
      </div>

      <section className="dashboard-audio-summary" aria-label="Generare audio">
        <div>
          <div className="piece-card-kicker">Generare audio</div>
          {quotaState.loading ? (
            <p>Se încarcă limita de generare audio...</p>
          ) : canRequestAudio ? (
            <p>
              {formatNumber(quota.used)} / {formatNumber(quota.limit)} caractere folosite
              {quota.period_end ? ` până la ${formatDateTime(quota.period_end)}` : ""}.
              {" "}Disponibil: {formatNumber(remaining)} caractere.
              {" "}{user.has_author_audio_access ? "Poți încărca și lecturi de autor pentru textele aprobate." : "Încărcarea lecturilor de autor este disponibilă pentru Rapsod."}
            </p>
          ) : (
            <p>Generarea audio manuală include o cotă lunară de pornire pentru fiecare cont. Încărcarea lecturilor de autor este disponibilă pentru Rapsod.</p>
          )}
        </div>
      </section>
      <section className="dashboard-audio-summary" aria-label="Diacritice">
        <div>
          <div className="piece-card-kicker">Diacritice</div>
          {diacriticsQuotaState.loading ? (
            <p>Se încarcă limita pentru Diacritice...</p>
          ) : diacriticsQuota ? (
            <p>
              {formatNumber(diacriticsQuota.used)} / {formatNumber(diacriticsQuota.limit)} caractere folosite
              {diacriticsQuota.period_end ? ` până la ${formatDateTime(diacriticsQuota.period_end)}` : ""}.
              {" "}Disponibil: {formatNumber(diacriticsQuota.remaining)} caractere.
            </p>
          ) : (
            <p>Diacriticele sunt disponibile după autentificare.</p>
          )}
        </div>
      </section>
      {diacriticsQuotaState.error ? <div className="inline-error">{diacriticsQuotaState.error}</div> : null}
      {quotaState.error ? <div className="inline-error">{quotaState.error}</div> : null}
      {promotionsState.error ? <div className="inline-error">{promotionsState.error}</div> : null}
      {status?.text ? <div className={status.kind === "error" ? "inline-error" : "inline-status"}>{status.text}</div> : null}

      <SeriesManagerPanel posts={posts} user={user} />

      <section className="dashboard-posts-panel" aria-label="Postări și ciorne">
        <div className="dashboard-posts-head">
          <div className="dashboard-tabs" role="tablist" aria-label="Tip texte">
            <button className={activeTab === "posts" ? "active" : ""} type="button" role="tab" aria-selected={activeTab === "posts"} onClick={() => setActiveTab("posts")}>
              Postări
            </button>
            <button className={activeTab === "drafts" ? "active" : ""} type="button" role="tab" aria-selected={activeTab === "drafts"} onClick={() => setActiveTab("drafts")}>
              Ciorne
            </button>
          </div>
          <span className="dashboard-count">
            {activeTab === "posts" ? `${formatNumber(postTotal)} postări` : `${formatNumber(draftTotal)} ciorne`}
          </span>
        </div>

        {activeTab === "posts" ? (
          <>
            {loading ? <p className="auth-sub">Se încarcă postările...</p> : null}
            {error ? <div className="inline-error">{error}</div> : null}
            {posts.length ? (
              <div className="dashboard-list">
                {posts.map((post) => (
                  <DashboardPostCard
                    key={post.id}
                    post={post}
                    user={user}
                    canRequestAudio={canRequestAudio}
                    remaining={remaining}
                    busy={audioBusyId === post.id}
                    authorAudioBusy={authorAudioBusyId === post.id}
                    deleting={deletingPostId === post.id}
                    promoted={promotedOwnPostIds.has(post.id)}
                    promotionBusy={promotionBusyId === post.id}
                    promotionLoading={promotionsState.loading && !promotionSnapshot}
                    promotionLimit={promotionLimits.own_posts || 2}
                    promotionLimitReached={promotedOwnPosts.length >= Number(promotionLimits.own_posts || 2)}
                    onConvert={() => convertPostToAudio(post)}
                    onAuthorAudioUpload={(file) => uploadAuthorAudio(post, file)}
                    onTogglePromotion={() => togglePostPromotion(post)}
                    onDelete={() => removePost(post)}
                  />
                ))}
              </div>
            ) : !loading && !error ? <p className="auth-sub">Nu ai postări încă.</p> : null}
            <DashboardPager page={postPage} total={postTotal} onPageChange={setPostPage} />
          </>
        ) : (
          <>
            {draftState.loading ? <p className="auth-sub">Se încarcă ciornele...</p> : null}
            {draftState.error ? <div className="inline-error">{draftState.error}</div> : null}
            {drafts.length ? (
              <div className="dashboard-list">
                {drafts.map((draft) => (
                  <DashboardDraftCard
                    key={draft.id}
                    draft={draft}
                    user={user}
                    busy={draftBusyId === draft.id}
                    onDiscard={() => discardDraft(draft)}
                  />
                ))}
              </div>
            ) : !draftState.loading && !draftState.error ? <p className="auth-sub">Nu ai ciorne salvate.</p> : null}
            <DashboardPager page={draftPage} total={draftTotal} onPageChange={setDraftPage} />
          </>
        )}
      </section>
    </PageShell>
  );
}

function SeriesCreateModal({ open, busy, form, onChange, onClose, onSubmit }) {
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="access-modal-scrim" role="presentation" onClick={onClose}>
      <section className="access-modal" role="dialog" aria-modal="true" aria-labelledby="series-create-title" onClick={(event) => event.stopPropagation()}>
        <button className="access-modal-close" type="button" aria-label="Închide" onClick={onClose}>
          <FiX aria-hidden="true" />
        </button>
        <div className="piece-card-kicker">serii</div>
        <h2 id="series-create-title" className="access-modal-title">Creează serie</h2>
        <form className="series-create-modal-form" onSubmit={onSubmit}>
          <label className="auth-field">
            Titlu serie
            <input
              className="cal-input"
              value={form.title}
              maxLength={TITLE_CHARACTER_LIMIT}
              onChange={(event) => onChange((current) => ({ ...current, title: event.target.value }))}
            />
          </label>
          <label className="auth-field">
            Descriere opțională
            <textarea
              className="cal-input"
              value={form.description}
              maxLength={2000}
              rows={4}
              onChange={(event) => onChange((current) => ({ ...current, description: event.target.value }))}
            />
          </label>
          <div className="button-row">
            <button className="cal-btn primary" type="submit" disabled={busy === "create" || !form.title.trim()}>
              <FiPlus aria-hidden="true" />
              {busy === "create" ? "Se creează..." : "Creează"}
            </button>
            <button className="cal-btn" type="button" onClick={onClose}>Închide</button>
          </div>
        </form>
      </section>
    </div>
  );
}

function SeriesManagerPanel({ posts, user }) {
  const [refreshKey, setRefreshKey] = useState(0);
  const [selectedSeriesId, setSelectedSeriesId] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({ title: "", description: "" });
  const [editForm, setEditForm] = useState({ title: "", description: "" });
  const [postToAdd, setPostToAdd] = useState("");
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");
  const seriesState = useAsync(
    () => (user ? fetchMySeries() : Promise.resolve({ series: [] })),
    [user?.id, refreshKey]
  );
  const seriesList = seriesState.data?.series ?? [];
  const selectedSeries = seriesList.find((item) => String(item.id) === String(selectedSeriesId)) || seriesList[0] || null;
  const activeSeriesId = selectedSeries ? String(selectedSeries.id) : "";
  const managedState = useAsync(
    () => (activeSeriesId ? fetchManagedSeries(activeSeriesId) : Promise.resolve(null)),
    [activeSeriesId, refreshKey]
  );
  const entries = managedState.data?.posts ?? [];
  const entryPostIds = new Set(entries.map((entry) => entry.post_id));
  const availablePosts = (posts || []).filter((post) => !entryPostIds.has(post.id));

  useEffect(() => {
    if (!seriesList.length) {
      if (selectedSeriesId) setSelectedSeriesId("");
      return;
    }
    if (!selectedSeriesId || !seriesList.some((item) => String(item.id) === String(selectedSeriesId))) {
      setSelectedSeriesId(String(seriesList[0].id));
    }
  }, [seriesList, selectedSeriesId]);

  useEffect(() => {
    setEditForm({
      title: selectedSeries?.title || "",
      description: selectedSeries?.description || ""
    });
  }, [selectedSeries?.id, selectedSeries?.title, selectedSeries?.description]);

  const refreshSeries = () => setRefreshKey((key) => key + 1);

  const createNewSeries = async (event) => {
    event.preventDefault();
    const title = createForm.title.trim();
    if (!title || busy) return;
    setBusy("create");
    setStatus("");
    try {
      const created = await createSeries({
        title,
        description: createForm.description.trim() || null
      });
      setCreateForm({ title: "", description: "" });
      setCreateOpen(false);
      setSelectedSeriesId(String(created.id));
      setStatus("Seria a fost creată.");
      refreshSeries();
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut crea seria.");
    } finally {
      setBusy("");
    }
  };

  const saveSelectedSeries = async (event) => {
    event.preventDefault();
    if (!activeSeriesId || busy) return;
    setBusy("save");
    setStatus("");
    try {
      await updateSeries(activeSeriesId, {
        title: editForm.title.trim(),
        description: editForm.description.trim() || null
      });
      setStatus("Seria a fost actualizată.");
      refreshSeries();
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut actualiza seria.");
    } finally {
      setBusy("");
    }
  };

  const deleteSelectedSeries = async () => {
    if (!activeSeriesId || busy) return;
    if (!window.confirm(`Ștergi definitiv seria "${selectedSeries?.title || activeSeriesId}"?`)) return;
    setBusy("delete");
    setStatus("");
    try {
      await deleteSeries(activeSeriesId);
      setSelectedSeriesId("");
      setStatus("Seria a fost ștearsă.");
      refreshSeries();
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut șterge seria.");
    } finally {
      setBusy("");
    }
  };

  const addSelectedPost = async () => {
    if (!activeSeriesId || !postToAdd || busy) return;
    setBusy("add");
    setStatus("");
    try {
      await addPostToSeries(activeSeriesId, { post_id: Number(postToAdd) });
      setPostToAdd("");
      setStatus("Postarea a fost adăugată în serie.");
      refreshSeries();
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut adăuga postarea.");
    } finally {
      setBusy("");
    }
  };

  const removeEntry = async (entry) => {
    if (!activeSeriesId || busy) return;
    setBusy(`remove:${entry.post_id}`);
    setStatus("");
    try {
      await removePostFromSeries(activeSeriesId, entry.post_id);
      setStatus("Postarea a fost scoasă din serie.");
      refreshSeries();
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut scoate postarea.");
    } finally {
      setBusy("");
    }
  };

  const moveEntry = async (index, direction) => {
    if (!activeSeriesId || busy) return;
    const nextIndex = index + direction;
    if (nextIndex < 0 || nextIndex >= entries.length) return;
    const orderedIds = entries.map((entry) => entry.post_id);
    [orderedIds[index], orderedIds[nextIndex]] = [orderedIds[nextIndex], orderedIds[index]];
    setBusy("reorder");
    setStatus("");
    try {
      await reorderSeriesPosts(activeSeriesId, orderedIds);
      refreshSeries();
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut reordona seria.");
    } finally {
      setBusy("");
    }
  };

  return (
    <section className="series-manager" aria-label="Serii">
      <div className="draft-panel-head">
        <div>
          <div className="piece-card-kicker">serii</div>
          <h2>Serii și volume</h2>
        </div>
        <div className="series-head-actions">
          {selectedSeries?.slug ? <a className="cal-btn" href={mainPath(`/serii/${selectedSeries.slug}`)}>Vezi seria</a> : null}
          <button className="cal-btn primary" type="button" onClick={() => setCreateOpen(true)}>
            <FiPlus aria-hidden="true" />
            Creează
          </button>
        </div>
      </div>
      <SeriesCreateModal
        open={createOpen}
        busy={busy}
        form={createForm}
        onChange={setCreateForm}
        onClose={() => setCreateOpen(false)}
        onSubmit={createNewSeries}
      />
      {seriesState.loading ? <p className="auth-sub">Se încarcă seriile...</p> : null}
      {seriesState.error ? <div className="inline-error">{seriesState.error}</div> : null}
      {status ? <div className={status.includes("Nu am putut") ? "inline-error" : "inline-status"}>{status}</div> : null}
      {seriesList.length ? (
        <div className="series-manager-grid">
          <div className="series-selector-list" role="listbox" aria-label="Alege seria">
            {seriesList.map((item) => (
              <button
                className={`series-selector ${String(item.id) === activeSeriesId ? "active" : ""}`}
                key={item.id}
                type="button"
                onClick={() => setSelectedSeriesId(String(item.id))}
              >
                <span>{item.title}</span>
                <small>{formatNumber(item.post_count)} texte</small>
              </button>
            ))}
          </div>
          <div className="series-editor">
            <form className="series-edit-form" onSubmit={saveSelectedSeries}>
              <input
                className="cal-input"
                value={editForm.title}
                maxLength={TITLE_CHARACTER_LIMIT}
                onChange={(event) => setEditForm((current) => ({ ...current, title: event.target.value }))}
              />
              <textarea
                className="cal-input"
                value={editForm.description}
                maxLength={2000}
                rows={3}
                onChange={(event) => setEditForm((current) => ({ ...current, description: event.target.value }))}
              />
              <div className="button-row">
                <button className="cal-btn primary" type="submit" disabled={busy === "save" || !editForm.title.trim()}>
                  {busy === "save" ? "Se salvează..." : "Salvează"}
                </button>
                <button className="cal-btn danger" type="button" onClick={deleteSelectedSeries} disabled={busy === "delete"}>
                  <FiTrash2 aria-hidden="true" />
                  {busy === "delete" ? "Se șterge..." : "Șterge"}
                </button>
              </div>
            </form>
            <div className="series-add-row">
              <select className="cal-input" value={postToAdd} onChange={(event) => setPostToAdd(event.target.value)}>
                <option value="">Alege o postare</option>
                {availablePosts.map((post) => (
                  <option key={post.id} value={post.id}>{post.title} · {categoryLabel(post.category)}</option>
                ))}
              </select>
              <button className="cal-btn" type="button" onClick={addSelectedPost} disabled={!postToAdd || busy === "add"}>
                <FiPlus aria-hidden="true" />
                {busy === "add" ? "Se adaugă..." : "Adaugă"}
              </button>
            </div>
            {managedState.loading ? <p className="auth-sub">Se încarcă postările seriei...</p> : null}
            {managedState.error ? <div className="inline-error">{managedState.error}</div> : null}
            {entries.length ? (
              <div className="series-entry-list">
                {entries.map((entry, index) => (
                  <article className="series-entry" key={entry.id}>
                    <div>
                      <span className="piece-card-kicker">{formatNumber(index + 1)} · {categoryLabel(entry.post?.category)}</span>
                      <h3><a href={entry.post ? postHref(entry.post) : "#"}>{entry.post?.title || "Postare"}</a></h3>
                      {entry.post?.moderation_status ? <span className={`piece-card-status status-${entry.post.moderation_status}`.trim()}>{entry.post.moderation_status}</span> : null}
                    </div>
                    <div className="series-entry-actions">
                      <button className="icon-btn" type="button" aria-label="Mută în sus" onClick={() => moveEntry(index, -1)} disabled={index === 0 || busy === "reorder"}>
                        <FiArrowUp aria-hidden="true" />
                      </button>
                      <button className="icon-btn" type="button" aria-label="Mută în jos" onClick={() => moveEntry(index, 1)} disabled={index === entries.length - 1 || busy === "reorder"}>
                        <FiArrowDown aria-hidden="true" />
                      </button>
                      <button className="icon-btn danger" type="button" aria-label="Scoate din serie" onClick={() => removeEntry(entry)} disabled={busy === `remove:${entry.post_id}`}>
                        <FiTrash2 aria-hidden="true" />
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            ) : !managedState.loading ? <p className="auth-sub">Seria nu are postări încă.</p> : null}
          </div>
        </div>
      ) : !seriesState.loading ? <p className="auth-sub">Creează o serie, apoi adaugă postările tale în ordinea dorită.</p> : null}
    </section>
  );
}

function AuthorAudioUploadButton({ post, busy, disabled, onUpload }) {
  const inputRef = useRef(null);
  const canUpload = Boolean(post.author_audio_can_upload);
  const uploadDisabled = disabled || busy || !canUpload;
  const status = post.author_audio_status || "missing";
  const label = busy
    ? "Se încarcă..."
    : status === "ready"
      ? "Înlocuiește lectura"
      : status === "missing"
        ? "Încarcă lectura"
        : "Încarcă din nou";

  const pickFile = () => {
    if (!uploadDisabled) inputRef.current?.click();
  };

  const handleChange = (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (file) onUpload(file);
  };

  return (
    <>
      <input
        ref={inputRef}
        className="visually-hidden"
        type="file"
        accept={AUTHOR_AUDIO_ACCEPT}
        disabled={uploadDisabled}
        onChange={handleChange}
      />
      <button
        className="cal-btn"
        type="button"
        onClick={pickFile}
        disabled={uploadDisabled}
        title={canUpload ? undefined : "Disponibil pentru Rapsod după aprobarea postării"}
      >
        <FiUpload aria-hidden="true" />
        {label}
      </button>
    </>
  );
}

function DashboardPostCard({
  post,
  user,
  canRequestAudio,
  remaining,
  busy,
  authorAudioBusy,
  deleting,
  promoted,
  promotionBusy,
  promotionLoading,
  promotionLimit,
  promotionLimitReached,
  onConvert,
  onAuthorAudioUpload,
  onTogglePromotion,
  onDelete
}) {
  const href = postHref(post);
  const editHref = `${authorPath(user, "/scrie")}?post=${encodeURIComponent(post.id)}`;
  const characterCount = Number(post.audio_tts_character_count ?? 0);
  const audioReady = Boolean(post.audio_available && post.audio_playback_url);
  const convertDisabled = busy || deleting || !canRequestAudio || !post.audio_can_request || characterCount > remaining;
  const showAuthorAudio = Boolean(user?.has_author_audio_access);
  const showAuthorAudioStatus = showAuthorAudio && post.author_audio_message;
  const moderationOverlayText = MODERATING_STATUSES.has(post.moderation_status) ? TEXT_MODERATION_MESSAGE : "";
  const canPromote = post.moderation_status === "approved";
  const promoteDisabled = promotionBusy || promotionLoading || deleting || !canPromote || (!promoted && promotionLimitReached);
  const promoteTitle = !canPromote
    ? "Poți promova doar textele aprobate"
    : !promoted && promotionLimitReached
      ? `Poți promova cel mult ${formatNumber(promotionLimit)} texte proprii`
      : promoted
        ? "Elimină textul din Călimara mea"
        : "Promovează textul în Călimara mea";

  return (
    <article className={`dashboard-post-card dashboard-owned-post-card ${moderationOverlayText ? "has-moderation-overlay" : ""}`.trim()}>
      <div className="dashboard-post-main">
        <div className="piece-card-kicker-row">
          <span className="piece-card-kicker">{categoryLabel(post.category)}</span>
        </div>
        <h2 className="piece-card-title"><a href={href}>{post.title}</a></h2>
        <div className={`piece-card-excerpt-wrap ${moderationOverlayText ? "has-moderation-overlay" : ""}`.trim()}>
          <p className="piece-card-excerpt">{htmlToText(post.content)}</p>
          {moderationOverlayText ? <ModerationOverlay className="piece-card-moderation-overlay">{moderationOverlayText}</ModerationOverlay> : null}
        </div>
        <div className="piece-card-meta">
          <span>{formatNumber(characterCount)} caractere</span>
          <span>{audioStatusLabel(post.audio_status)}</span>
          {post.created_at ? <span>{post.created_at}</span> : null}
        </div>
        {audioReady ? (
          <CompactAudioPlayer className="compact" src={post.audio_playback_url} downloadUrl={post.audio_id ? audioDownloadUrl(post.audio_id) : post.audio_playback_url} />
        ) : null}
        {showAuthorAudioStatus ? (
          <p className={`author-audio-status ${post.author_audio_status || "missing"}`.trim()}>
            {post.author_audio_message}
          </p>
        ) : null}
      </div>
      <div className="dashboard-card-actions">
        <a className="cal-btn" href={href}>
          <FiEye aria-hidden="true" />
          Vezi pe blog
        </a>
        <a className="cal-btn" href={editHref}>
          <FiEdit3 aria-hidden="true" />
          Editează
        </a>
        <button
          className={`cal-btn dashboard-promote-btn ${promoted ? "is-promoted" : ""}`.trim()}
          type="button"
          onClick={onTogglePromotion}
          disabled={promoteDisabled}
          title={promoteTitle}
        >
          <FiStar aria-hidden="true" />
          {promotionBusy ? "Se actualizează..." : promoted ? "Elimină promovarea" : "Promovează în Călimara mea"}
        </button>
        <button className="cal-btn danger" type="button" onClick={onDelete} disabled={deleting}>
          <FiTrash2 aria-hidden="true" />
          {deleting ? "Se șterge..." : "Șterge"}
        </button>
        <button className="cal-btn" type="button" onClick={onConvert} disabled={convertDisabled}>
          <FiHeadphones aria-hidden="true" />
          {busy ? "Se trimite..." : "Convertește în Audio"}
        </button>
        {showAuthorAudio ? (
          <AuthorAudioUploadButton
            post={post}
            busy={authorAudioBusy}
            disabled={deleting}
            onUpload={onAuthorAudioUpload}
          />
        ) : null}
      </div>
    </article>
  );
}

function DashboardDraftCard({ draft, user, busy, onDiscard }) {
  const title = draft.title?.trim() || "Ciornă fără titlu";
  const excerpt = htmlToText(draft.content) || "Fără text încă.";
  const href = `${authorPath(user, "/scrie")}?draft=${encodeURIComponent(draft.id)}`;

  return (
    <article className="dashboard-post-card dashboard-draft-card">
      <div className="dashboard-post-main">
        <div className="piece-card-kicker-row">
          <span className="piece-card-kicker">ciornă · {categoryLabel(draft.category)}</span>
          {draft.updated_at ? <span className="piece-card-status">{formatDateTime(draft.updated_at)}</span> : null}
        </div>
        <h2 className="piece-card-title"><a href={href}>{title}</a></h2>
        <p className="piece-card-excerpt">{excerpt}</p>
      </div>
      <div className="dashboard-card-actions">
        <a className="cal-btn primary" href={href}>
          <FiEdit3 aria-hidden="true" />
          Editează
        </a>
        <button className="cal-btn danger" type="button" onClick={onDiscard} disabled={busy}>
          <FiTrash2 aria-hidden="true" />
          {busy ? "Se șterge..." : "Șterge"}
        </button>
      </div>
    </article>
  );
}

export default function DashboardRoute({ user }) {
  return <DashboardView user={user} />;
}
