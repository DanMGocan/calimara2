import { useCallback, useEffect, useRef, useState } from "react";
import { FiArrowDown, FiArrowUp, FiPlus, FiTrash2 } from "react-icons/fi";
import { audioDownloadUrl, fetchAudioConversionQuota, requestTtsConversions } from "../api/audio.js";
import { createSeries, deleteSeries, fetchManagedSeries, fetchMySeries, addPostToSeries, removePostFromSeries, reorderSeriesPosts, updateSeries } from "../api/series.js";
import { deletePostDraft, fetchArchive, fetchPostDrafts } from "../api/posts.js";
import { TITLE_CHARACTER_LIMIT } from "../app/constants.js";
import { CompactAudioPlayer, postHref } from "../app/content.jsx";
import { audioStatusLabel, categoryLabel, formatDateTime, formatNumber, htmlToText, usernameHandle } from "../app/format.js";
import { useAsync } from "../app/hooks.js";
import { AuthRequired, PageShell, StatusPanel } from "../app/layout.jsx";
import { authorPath, mainPath } from "../app/paths.js";

function DashboardView({ user }) {
  const [refreshKey, setRefreshKey] = useState(0);
  const [draftRefreshKey, setDraftRefreshKey] = useState(0);
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const [status, setStatus] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [draftBusyId, setDraftBusyId] = useState(null);
  const [retryingPostId, setRetryingPostId] = useState(null);
  const { data, error, loading } = useAsync(
    () => (user ? fetchArchive() : Promise.resolve({ posts: [] })),
    [user?.id, refreshKey]
  );
  const draftState = useAsync(
    () => (user ? fetchPostDrafts() : Promise.resolve({ drafts: [] })),
    [user?.id, draftRefreshKey]
  );
  const quotaState = useAsync(
    () => (user ? fetchAudioConversionQuota() : Promise.resolve(null)),
    [user?.id, refreshKey]
  );

  if (!user) return <AuthRequired />;

  const posts = data?.posts ?? [];
  const drafts = draftState.data?.drafts ?? [];
  const quota = quotaState.data;
  const canRequestAudio = Boolean(quota?.can_request);
  const selectedPosts = posts.filter((post) => selectedIds.has(post.id));
  const selectedCharacters = selectedPosts.reduce((sum, post) => sum + Number(post.audio_tts_character_count ?? 0), 0);
  const remaining = Number(quota?.remaining ?? 0);
  const overQuota = selectedCharacters > remaining;

  const togglePost = (post, checked) => {
    setStatus("");
    setSelectedIds((current) => {
      const next = new Set(current);
      if (checked) next.add(post.id);
      else next.delete(post.id);
      return next;
    });
  };

  const submitAudioRequestIds = async (postIds, successMessage) => {
    if (!postIds.length || submitting) return;
    setSubmitting(true);
    setStatus("");
    try {
      const response = await requestTtsConversions(postIds);
      setSelectedIds((current) => {
        const next = new Set(current);
        postIds.forEach((postId) => next.delete(postId));
        return next;
      });
      setStatus(
        response.queued.length
          ? successMessage || `${response.queued.length} texte au fost trimise la generare audio.`
          : "Textele selectate aveau deja audio sau erau deja în coadă."
      );
      setRefreshKey((key) => key + 1);
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut porni generarea audio.");
    } finally {
      setSubmitting(false);
      setRetryingPostId(null);
    }
  };

  const submitAudioRequests = async () => {
    if (!selectedIds.size || overQuota || submitting) return;
    await submitAudioRequestIds([...selectedIds]);
  };

  const retryAudioRequest = async (post) => {
    const characterCount = Number(post.audio_tts_character_count ?? 0);
    if (submitting || !canRequestAudio || !post.audio_can_request || characterCount > remaining) return;
    setRetryingPostId(post.id);
    await submitAudioRequestIds([post.id], `„${post.title}” a fost retrimis la generare audio.`);
  };

  const discardDraft = async (draft) => {
    if (draftBusyId) return;
    setDraftBusyId(draft.id);
    setStatus("");
    try {
      await deletePostDraft(draft.id);
      setStatus("Ciorna a fost ștearsă.");
      setDraftRefreshKey((key) => key + 1);
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut șterge ciorna.");
    } finally {
      setDraftBusyId(null);
    }
  };

  return (
    <PageShell kicker="panou" title="Textele tale" sub={`Conectat ca ${usernameHandle(user.username)}.`}>
      <div className="dashboard-action-row">
        <a className="dashboard-write-btn" href={authorPath(user, "/scrie")}>
          <FiPlus aria-hidden="true" />
          <span>Scrie</span>
        </a>
      </div>
      <section className="audio-quota-panel" aria-label="Cotă generare audio">
        <div>
          <div className="piece-card-kicker">generare audio</div>
          {quotaState.loading ? (
            <p className="auth-sub">Se încarcă limita de generare audio...</p>
          ) : canRequestAudio ? (
            <p className="quota-line">
              {formatNumber(quota.used)} / {formatNumber(quota.limit)} caractere folosite
              {quota.period_end ? ` până la ${formatDateTime(quota.period_end)}` : ""}.
            </p>
          ) : (
            <p className="auth-sub">Generarea audio manuală este disponibilă pentru Cronicar și Rapsod.</p>
          )}
        </div>
        {quotaState.loading ? null : canRequestAudio ? (
          <div className="quota-actions">
            <span className={`quota-pill ${overQuota ? "danger" : ""}`}>
              Selectat: {formatNumber(selectedCharacters)} / {formatNumber(remaining)}
            </span>
            <button className="cal-btn primary" type="button" onClick={submitAudioRequests} disabled={!selectedIds.size || overQuota || submitting}>
              {submitting ? "Se trimite..." : "Generează audio"}
            </button>
          </div>
        ) : <a className="cal-btn" href={mainPath("/premium")}>Vezi Premium</a>}
      </section>
      {quotaState.error ? <div className="inline-error">{quotaState.error}</div> : null}
      {status ? <div className={status.includes("Nu am putut") || status.includes("depășită") ? "inline-error" : "inline-status"}>{status}</div> : null}
      {draftState.error ? <div className="inline-error">{draftState.error}</div> : null}
      {drafts.length ? (
        <section className="draft-panel" aria-label="Ciorne salvate">
          <div className="draft-panel-head">
            <div>
              <div className="piece-card-kicker">ciorne</div>
              <h2>Ciorne salvate</h2>
            </div>
          </div>
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
        </section>
      ) : null}
      <SeriesManagerPanel posts={posts} user={user} />
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca panoul">{error}</StatusPanel> : null}
      {data?.posts?.length ? (
        <div className="dashboard-list">
          {posts.map((post) => {
            const selected = selectedIds.has(post.id);
            const wouldExceed = !selected && selectedCharacters + Number(post.audio_tts_character_count ?? 0) > remaining;
            const retryWouldExceed = Number(post.audio_tts_character_count ?? 0) > remaining;
            const disabled = !canRequestAudio || !post.audio_can_request || wouldExceed || submitting;
            const retryDisabled = !canRequestAudio || !post.audio_can_request || retryWouldExceed || submitting;
            return (
              <DashboardPostCard
                key={post.id}
                post={post}
                selected={selected}
                disabled={disabled}
                onToggle={(checked) => togglePost(post, checked)}
                onRetry={() => retryAudioRequest(post)}
                retryDisabled={retryDisabled}
                retrying={retryingPostId === post.id}
              />
            );
          })}
        </div>
      ) : !loading && !error ? <StatusPanel title="Nu ai texte încă" /> : null}
    </PageShell>
  );
}
function SeriesManagerPanel({ posts, user }) {
  const [refreshKey, setRefreshKey] = useState(0);
  const [selectedSeriesId, setSelectedSeriesId] = useState("");
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
        {selectedSeries?.slug ? <a className="cal-btn" href={mainPath(`/serii/${selectedSeries.slug}`)}>Vezi seria</a> : null}
      </div>
      <form className="series-form" onSubmit={createNewSeries}>
        <input
          className="cal-input"
          value={createForm.title}
          maxLength={TITLE_CHARACTER_LIMIT}
          onChange={(event) => setCreateForm((current) => ({ ...current, title: event.target.value }))}
          placeholder="Titlu serie"
        />
        <input
          className="cal-input"
          value={createForm.description}
          maxLength={2000}
          onChange={(event) => setCreateForm((current) => ({ ...current, description: event.target.value }))}
          placeholder="Descriere opțională"
        />
        <button className="cal-btn primary" type="submit" disabled={busy === "create" || !createForm.title.trim()}>
          <FiPlus aria-hidden="true" />
          {busy === "create" ? "Se creează..." : "Creează"}
        </button>
      </form>
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
                      {entry.post?.moderation_status ? <span className="piece-card-status">{entry.post.moderation_status}</span> : null}
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
function DashboardPostCard({ post, selected, disabled, onToggle, onRetry, retryDisabled, retrying }) {
  const href = postHref(post);
  const characterCount = Number(post.audio_tts_character_count ?? 0);
  const audioReady = Boolean(post.audio_available && post.audio_playback_url);
  const canRetry = post.audio_status === "failed" && post.audio_can_request;
  return (
    <article className={`dashboard-post-card ${selected ? "selected" : ""}`}>
      <label className="dashboard-select">
        <input
          type="checkbox"
          checked={selected}
          disabled={disabled}
          onChange={(event) => onToggle(event.target.checked)}
        />
        <span>Selectează pentru audio</span>
      </label>
      <div className="dashboard-post-main">
        <div className="piece-card-kicker-row">
          <span className="piece-card-kicker">{categoryLabel(post.category)}</span>
          <span className="piece-card-status">{post.moderation_status}</span>
        </div>
        <h2 className="piece-card-title"><a href={href}>{post.title}</a></h2>
        <p className="piece-card-excerpt">{htmlToText(post.content)}</p>
        <div className="piece-card-meta">
          <span>{formatNumber(characterCount)} caractere</span>
          <span>{audioStatusLabel(post.audio_status)}</span>
          {post.created_at ? <span>{post.created_at}</span> : null}
        </div>
        {audioReady ? (
          <CompactAudioPlayer className="compact" src={post.audio_playback_url} downloadUrl={post.audio_id ? audioDownloadUrl(post.audio_id) : post.audio_playback_url} />
        ) : null}
        {canRetry ? (
          <div className="dashboard-audio-actions">
            <button className="cal-btn" type="button" onClick={onRetry} disabled={retryDisabled}>
              {retrying ? "Se retrimite..." : "Reîncearcă audio"}
            </button>
          </div>
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
      <div className="dashboard-draft-actions">
        <a className="cal-btn primary" href={href}>Continuă</a>
        <button className="cal-btn" type="button" onClick={onDiscard} disabled={busy}>
          {busy ? "Se șterge..." : "Șterge"}
        </button>
      </div>
    </article>
  );
}

export default function DashboardRoute({ user }) {
  return <DashboardView user={user} />;
}
