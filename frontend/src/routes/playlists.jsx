import { useEffect, useState } from "react";
import { FiPlay, FiRefreshCw, FiTrash2, FiX } from "react-icons/fi";
import { deleteAudioPlaylist, fetchAudioPlaylist, fetchAudioPlaylists, removePostFromAudioPlaylist, updateAudioPlaylist, createAudioPlaylist } from "../api/audio.js";
import { PostTitleLink } from "../app/content.jsx";
import { categoryLabel, formatNumber } from "../app/format.js";
import { PageShell, StatusPanel } from "../app/layout.jsx";
import { mainPath } from "../app/paths.js";

function PlaylistItemRow({ item, busy, onRemove }) {
  const post = {
    title: item.title,
    slug: item.slug,
    owner: { username: item.author_username },
  };
  return (
    <div className={`playlist-post-row ${item.audio_available ? "" : "is-unavailable"}`.trim()}>
      <span className="playlist-post-position">{item.position}</span>
      <span className="playlist-post-main">
        <strong><PostTitleLink post={post}>{item.title}</PostTitleLink></strong>
        <small>{categoryLabel(item.category)} · @{item.author_username}</small>
      </span>
      <button className="icon-btn playlist-icon-action" type="button" onClick={() => onRemove(item)} disabled={Boolean(busy)} aria-label="Șterge din playlist" title="Șterge din playlist">
        <FiX aria-hidden="true" />
      </button>
    </div>
  );
}

export default function PlaylistsRoute({ user, onStartPlaylistListening }) {
  const [playlists, setPlaylists] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [newTitle, setNewTitle] = useState("");
  const [editTitle, setEditTitle] = useState("");
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");

  const loadPlaylists = async (preferredId = selectedId) => {
    if (!user?.has_author_audio_access) return;
    setLoading(true);
    setStatus("");
    try {
      const data = await fetchAudioPlaylists();
      const items = Array.isArray(data?.playlists) ? data.playlists : [];
      setPlaylists(items);
      const nextId = preferredId && items.some((item) => item.id === preferredId)
        ? preferredId
        : items[0]?.id || null;
      setSelectedId(nextId);
      if (!nextId) {
        setDetail(null);
        setEditTitle("");
      }
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut încărca playlisturile.");
    } finally {
      setLoading(false);
    }
  };

  const loadDetail = async (playlistId) => {
    if (!playlistId || !user?.has_author_audio_access) return;
    setDetailLoading(true);
    setStatus("");
    try {
      const data = await fetchAudioPlaylist(playlistId);
      setDetail(data);
      setEditTitle(data.title || "");
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut încărca playlistul.");
    } finally {
      setDetailLoading(false);
    }
  };

  useEffect(() => {
    loadPlaylists();
  }, [user?.id, user?.has_author_audio_access]);

  useEffect(() => {
    if (selectedId) loadDetail(selectedId);
  }, [selectedId]);

  if (!user?.has_author_audio_access) {
    return (
      <PageShell kicker="playlisturi" title="Playlisturi audio" sub="Disponibil pentru Rapsod.">
        <StatusPanel title="Necesită Rapsod">
          <a className="cal-btn primary" href={mainPath("/premium")}>Vezi Premium</a>
        </StatusPanel>
      </PageShell>
    );
  }

  const createPlaylist = async (event) => {
    event.preventDefault();
    const title = newTitle.trim();
    if (!title) return;
    setBusy("create");
    setStatus("");
    try {
      const created = await createAudioPlaylist(title);
      setNewTitle("");
      await loadPlaylists(created.id);
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut crea playlistul.");
    } finally {
      setBusy("");
    }
  };

  const renamePlaylist = async (event) => {
    event.preventDefault();
    const title = editTitle.trim();
    if (!detail?.id || !title) return;
    setBusy("rename");
    setStatus("");
    try {
      const updated = await updateAudioPlaylist(detail.id, title);
      setDetail(updated);
      setEditTitle(updated.title || "");
      setPlaylists((current) => current.map((item) => item.id === updated.id ? { ...item, title: updated.title } : item));
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut redenumi playlistul.");
    } finally {
      setBusy("");
    }
  };

  const deletePlaylist = async () => {
    if (!detail?.id) return;
    setBusy("delete");
    setStatus("");
    try {
      await deleteAudioPlaylist(detail.id);
      await loadPlaylists(null);
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut șterge playlistul.");
    } finally {
      setBusy("");
    }
  };

  const removeItem = async (item) => {
    if (!detail?.id || !item?.post_id) return;
    setBusy(`remove:${item.post_id}`);
    setStatus("");
    try {
      await removePostFromAudioPlaylist(detail.id, item.post_id);
      await loadPlaylists(detail.id);
      await loadDetail(detail.id);
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut șterge postarea din playlist.");
    } finally {
      setBusy("");
    }
  };

  const tracksAvailable = Number(detail?.items?.filter((item) => item.audio_available).length || 0);

  return (
    <PageShell kicker="playlisturi" title="Playlisturi audio" sub="Colecții private pentru playerul audio.">
      <div className="playlist-page">
        <section className="playlist-sidebar" aria-label="Playlisturi">
          <form className="playlist-create-form" onSubmit={createPlaylist}>
            <input className="cal-input" value={newTitle} onChange={(event) => setNewTitle(event.target.value)} maxLength={120} placeholder="Playlist nou" aria-label="Titlu playlist nou" />
            <button className="cal-btn primary" type="submit" disabled={busy === "create" || !newTitle.trim()}>Creează</button>
          </form>
          <button className="cal-btn playlist-refresh" type="button" onClick={() => loadPlaylists()} disabled={loading || Boolean(busy)}>
            <FiRefreshCw aria-hidden="true" />
            <span>Reîncarcă</span>
          </button>
          {loading ? <StatusPanel title="Se încarcă" /> : null}
          {!loading && playlists.length ? (
            <div className="playlist-list">
              {playlists.map((playlist) => (
                <button
                  className={`playlist-list-item ${playlist.id === selectedId ? "active" : ""}`.trim()}
                  type="button"
                  key={playlist.id}
                  onClick={() => setSelectedId(playlist.id)}
                >
                  <strong>{playlist.title}</strong>
                  <span>{formatNumber(playlist.item_count)} texte</span>
                </button>
              ))}
            </div>
          ) : null}
          {!loading && !playlists.length ? <StatusPanel title="Nu ai playlisturi încă" /> : null}
        </section>
        <section className="playlist-detail" aria-label="Detalii playlist">
          {status ? <p className="inline-error">{status}</p> : null}
          {detailLoading ? <StatusPanel title="Se încarcă playlistul" /> : null}
          {detail && !detailLoading ? (
            <>
              <div className="playlist-detail-head">
                <div>
                  <div className="piece-card-kicker">playlist privat</div>
                  <h2>{detail.title}</h2>
                  <p>{formatNumber(detail.item_count)} texte · {formatNumber(tracksAvailable)} redabile</p>
                </div>
                <div className="playlist-detail-actions">
                  <button className="cal-btn primary" type="button" onClick={() => onStartPlaylistListening?.(detail)} disabled={!tracksAvailable || Boolean(busy)}>
                    <FiPlay aria-hidden="true" />
                    <span>Play</span>
                  </button>
                  <button className="cal-btn danger" type="button" onClick={deletePlaylist} disabled={busy === "delete"}>
                    <FiTrash2 aria-hidden="true" />
                    <span>Șterge</span>
                  </button>
                </div>
              </div>
              <form className="playlist-rename-form" onSubmit={renamePlaylist}>
                <input className="cal-input" value={editTitle} onChange={(event) => setEditTitle(event.target.value)} maxLength={120} aria-label="Redenumește playlist" />
                <button className="cal-btn" type="submit" disabled={busy === "rename" || !editTitle.trim()}>Salvează</button>
              </form>
              {detail.items?.length ? (
                <div className="playlist-post-list">
                  {detail.items.map((item) => (
                    <PlaylistItemRow key={item.id} item={item} busy={busy === `remove:${item.post_id}`} onRemove={removeItem} />
                  ))}
                </div>
              ) : (
                <StatusPanel title="Playlist gol">Adaugă texte din meniul de acțiuni al unei postări cu audio.</StatusPanel>
              )}
            </>
          ) : null}
        </section>
      </div>
    </PageShell>
  );
}
