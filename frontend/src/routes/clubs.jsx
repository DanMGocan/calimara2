import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { FiAward, FiCheck, FiChevronDown, FiEdit3, FiImage, FiLock, FiMessageCircle, FiPlus, FiSearch, FiSend, FiStar, FiTrash2, FiUpload, FiUserPlus, FiUsers, FiX } from "react-icons/fi";
import {
  applyToClub,
  clearClubFeatured,
  createClub,
  createClubBoardMessage,
  deleteClubBoardMessage,
  deleteClubMedia,
  fetchClub,
  fetchClubBoard,
  fetchClubRequests,
  fetchClubs,
  fetchMyClubs,
  inviteToClub,
  respondClubRequest,
  uploadClubMedia
} from "../api/clubs.js";
import { AuthorLink } from "../app/content.jsx";
import { categoryLabel, formatDateTime, usernameHandle } from "../app/format.js";
import { useAsync } from "../app/hooks.js";
import { AdSlot, PageShell, StatusPanel } from "../app/layout.jsx";
import { avatarPreviewUrl, blogUrl, coverPreviewUrl, mainPath } from "../app/paths.js";
import { PROFILE_TIER_BADGES } from "../app/constants.js";

const JOIN_POLICY_LABELS = {
  open: "Deschis",
  private: "Cu cerere",
  closed: "Pe invitație"
};

const EMPTY_CREATE_FORM = {
  title: "",
  description: "",
  theme: "",
  motto: "",
  speciality: "poezie",
  join_policy: "private"
};

const CLUB_ROLE_LABELS = {
  owner: "creator",
  admin: "administrator",
  member: "membru"
};

const CLUB_ACHIEVEMENT_ICONS = {
  atelier_deschis: FiEdit3,
  cerc_de_cinci: FiUsers,
  dialog_viu: FiMessageCircle,
  creatia_saptamanii: FiStar
};

function roleLabel(role) {
  return CLUB_ROLE_LABELS[role] || role || "membru";
}

function ClubAchievementCard({ achievement }) {
  const Icon = CLUB_ACHIEVEMENT_ICONS[achievement.key] || FiAward;
  return (
    <article className="club-achievement">
      <div className="club-achievement-icon" aria-hidden="true">
        <Icon />
      </div>
      <div className="club-achievement-body">
        <strong>{achievement.label}</strong>
        <span>{achievement.description}</span>
        <small>Obtinut la: {formatDateTime(achievement.unlocked_at)}</small>
      </div>
    </article>
  );
}

function ownerTierClass(club) {
  const owner = club?.owner || {};
  const tier = owner?.is_premium ? owner?.premium_tier || "trubadur" : "free";
  return (PROFILE_TIER_BADGES[tier] || PROFILE_TIER_BADGES.free).className;
}

function ClubAvatar({ club, size = "normal" }) {
  const seed = club.avatar_seed || `${club.slug || club.title || "club"}-shapes`;
  const src = club.profile_photo_url || club.avatar_url || avatarPreviewUrl(seed, size === "large" ? 160 : 96);
  return <img className={`club-avatar ${size} ${ownerTierClass(club)}`} src={src} alt="" />;
}

function policyText(club) {
  if (club.join_policy === "open") return "Orice autor autentificat poate intra direct.";
  if (club.join_policy === "closed") return "Intrarea se face doar pe bază de invitație.";
  return "Autorii trimit o cerere scurtă, iar echipa clubului o aprobă.";
}

function ClubCard({ club, user, applicationText, onApplicationText, onJoin, busy }) {
  const isMember = Boolean(club.my_role);
  const isPending = Boolean(club.my_pending_request_status);
  const canOpen = isMember || user?.is_admin;
  return (
    <article className="piece-card club-card">
      <div className="club-card-head">
        <ClubAvatar club={club} />
        <div>
          <div className="piece-card-kicker">{categoryLabel(club.speciality)} · {JOIN_POLICY_LABELS[club.join_policy] || "Club"}</div>
          <h2 className="piece-card-title">
            {canOpen ? (
              <a className="post-title-link" href={mainPath(`/cluburi/${club.slug}`)}>{club.title}</a>
            ) : club.title}
          </h2>
        </div>
      </div>
      <p className="piece-card-excerpt">{club.description || club.motto || "Club literar pe călimara.ro."}</p>
      {club.theme ? <p className="club-theme">Tema: {club.theme}</p> : null}
      <div className="piece-card-meta">
        <span>{club.member_count} membri</span>
        {club.owner?.username ? <AuthorLink user={club.owner} /> : null}
      </div>
      <p className="club-policy">{policyText(club)}</p>
      <div className="club-card-actions">
        {canOpen ? (
          <a className="cal-btn primary" href={mainPath(`/cluburi/${club.slug}`)}>
            <FiMessageCircle aria-hidden="true" />Deschide
          </a>
        ) : null}
        {!canOpen && club.join_policy === "open" ? (
          <button className="cal-btn primary" type="button" disabled={busy} onClick={() => onJoin(club)}>
            <FiUserPlus aria-hidden="true" />Intră în club
          </button>
        ) : null}
        {!canOpen && club.join_policy === "private" && !isPending ? (
          <div className="club-apply-box">
            <label className="cal-label" htmlFor={`apply-${club.id}`}>De ce vrei să ni te alături</label>
            <textarea
              id={`apply-${club.id}`}
              className="cal-textarea compact"
              value={applicationText || ""}
              onChange={(event) => onApplicationText(club.id, event.target.value)}
            />
            <button className="cal-btn primary" type="button" disabled={busy || !(applicationText || "").trim()} onClick={() => onJoin(club)}>
              <FiSend aria-hidden="true" />Trimite cererea
            </button>
          </div>
        ) : null}
        {!canOpen && isPending ? <span className="club-state-pill">Cerere trimisă</span> : null}
        {!canOpen && club.join_policy === "closed" ? (
          <span className="club-state-pill locked"><FiLock aria-hidden="true" />Doar invitație</span>
        ) : null}
      </div>
    </article>
  );
}

function ClubsView({ user }) {
  const [query, setQuery] = useState("");
  const [createForm, setCreateForm] = useState(EMPTY_CREATE_FORM);
  const [status, setStatus] = useState("");
  const [busyKey, setBusyKey] = useState("");
  const [applicationTexts, setApplicationTexts] = useState({});
  const [reloadKey, setReloadKey] = useState(0);
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [createOpen, setCreateOpen] = useState(false);

  useEffect(() => {
    const timeout = window.setTimeout(() => setDebouncedQuery(query.trim()), 240);
    return () => window.clearTimeout(timeout);
  }, [query]);

  const { data, error, loading } = useAsync(
    () => fetchClubs({ q: debouncedQuery }),
    [debouncedQuery, reloadKey]
  );
  const myState = useAsync(fetchMyClubs, [reloadKey]);
  const myClubs = myState.data?.clubs || [];
  const ownedClub = myState.data?.owned_club
    || myClubs.find((club) => club.my_role === "owner" || club.owner_id === user?.id)
    || data?.clubs?.find((club) => club.my_role === "owner" || club.owner_id === user?.id)
    || null;
  const canCreateClub = Boolean(!myState.loading && !ownedClub);

  const submitCreate = async (event) => {
    event.preventDefault();
    if (!canCreateClub) {
      setStatus("Poți crea un singur club.");
      setCreateOpen(false);
      return;
    }
    setStatus("");
    setBusyKey("create");
    try {
      await createClub(createForm);
      setCreateForm(EMPTY_CREATE_FORM);
      setCreateOpen(false);
      setReloadKey((value) => value + 1);
    } catch (error) {
      setStatus(error.message || "Nu am putut crea clubul.");
    } finally {
      setBusyKey("");
    }
  };

  const joinClub = async (club) => {
    setStatus("");
    setBusyKey(`join-${club.id}`);
    try {
      const payload = club.join_policy === "private"
        ? { application_text: (applicationTexts[club.id] || "").trim() }
        : {};
      await applyToClub(club.id, payload);
      setApplicationTexts((current) => ({ ...current, [club.id]: "" }));
      setReloadKey((value) => value + 1);
    } catch (error) {
      setStatus(error.message || "Nu am putut trimite cererea.");
    } finally {
      setBusyKey("");
    }
  };

  return (
    <PageShell kicker="cluburi" title="Cluburi literare" sub="Spații private de atelier, feedback și lucru pe texte, organizate în jurul unei teme.">
      <section className="club-section">
        <div className="club-section-head">
          <div>
            <h2>Cluburile mele</h2>
            <p>Cluburile în care poți intra direct.</p>
          </div>
          {ownedClub ? (
            <a className="cal-btn primary" href={mainPath(`/cluburi/${ownedClub.slug}`)}>
              <FiMessageCircle aria-hidden="true" />Clubul creat de tine
            </a>
          ) : null}
        </div>
        {myState.loading ? <StatusPanel title="Se încarcă" /> : null}
        {myState.error ? <StatusPanel title="Nu am putut încărca lista ta">{myState.error}</StatusPanel> : null}
        {myClubs.length ? (
          <div className="club-my-list">
            {myClubs.map((club) => (
              <a className="club-my-item" key={club.id} href={mainPath(`/cluburi/${club.slug}`)}>
                <ClubAvatar club={club} size="small" />
                <span>{club.title}</span>
                <small>{roleLabel(club.my_role)}</small>
              </a>
            ))}
          </div>
        ) : !myState.loading && !myState.error ? <p className="club-empty-note">Nu faci parte încă din niciun club.</p> : null}
      </section>

      <section className={`club-section club-create-panel ${createOpen ? "open" : ""}`.trim()}>
        <div className="club-section-head">
          <div>
            <h2>Creează un club</h2>
            <p>Fiecare utilizator poate crea un singur club.</p>
          </div>
          {canCreateClub ? (
            <button
              className="cal-btn club-create-toggle"
              type="button"
              aria-expanded={createOpen}
              aria-controls="club-create-form"
              onClick={() => setCreateOpen((open) => !open)}
            >
              {createOpen ? <FiX aria-hidden="true" /> : <FiPlus aria-hidden="true" />}
              {createOpen ? "Închide" : "Creează"}
              <FiChevronDown className="club-create-chevron" aria-hidden="true" />
            </button>
          ) : null}
        </div>
        {myState.loading ? (
          <StatusPanel title="Se verifică">Verificăm dacă ai deja un club creat.</StatusPanel>
        ) : ownedClub ? (
          <StatusPanel title="Ai deja un club">Poți administra clubul „{ownedClub.title}” din pagina lui.</StatusPanel>
        ) : createOpen ? (
          <form id="club-create-form" className="club-create-form" onSubmit={submitCreate}>
            <label className="cal-label">
              Nume
              <input className="cal-input" value={createForm.title} maxLength={120} required onChange={(event) => setCreateForm((current) => ({ ...current, title: event.target.value }))} />
            </label>
            <label className="cal-label">
              Descriere
              <textarea className="cal-textarea compact" value={createForm.description} maxLength={2000} onChange={(event) => setCreateForm((current) => ({ ...current, description: event.target.value }))} />
            </label>
            <label className="cal-label">
              Tema clubului
              <input className="cal-input" value={createForm.theme} maxLength={200} onChange={(event) => setCreateForm((current) => ({ ...current, theme: event.target.value }))} />
            </label>
            <label className="cal-label">
              Motto
              <input className="cal-input" value={createForm.motto} maxLength={200} onChange={(event) => setCreateForm((current) => ({ ...current, motto: event.target.value }))} />
            </label>
            <div className="club-create-row">
              <label className="cal-label">
                Domeniu
                <select className="cal-input" value={createForm.speciality} onChange={(event) => setCreateForm((current) => ({ ...current, speciality: event.target.value }))}>
                  <option value="poezie">Poezie</option>
                  <option value="proza_scurta">Proză scurtă</option>
                </select>
              </label>
              <label className="cal-label">
                Înscriere
                <select className="cal-input" value={createForm.join_policy} onChange={(event) => setCreateForm((current) => ({ ...current, join_policy: event.target.value }))}>
                  <option value="open">Deschis</option>
                  <option value="private">Cu cerere</option>
                  <option value="closed">Pe invitație</option>
                </select>
              </label>
            </div>
            <button className="cal-btn primary" type="submit" disabled={busyKey === "create" || !createForm.title.trim()}>
              <FiPlus aria-hidden="true" />Creează clubul
            </button>
          </form>
        ) : (
          <p className="club-empty-note">Deschide containerul pentru a seta numele, tema și modul de înscriere.</p>
        )}
        {status ? <p className="club-status">{status}</p> : null}
      </section>

      <section className="club-section">
        <div className="club-section-head">
          <div>
            <h2>Descoperă cluburi</h2>
            <p>Caută după nume sau descriere.</p>
          </div>
          <label className="club-search">
            <FiSearch aria-hidden="true" />
            <input value={query} placeholder="Caută cluburi" onChange={(event) => setQuery(event.target.value)} />
          </label>
        </div>
        {loading ? <StatusPanel title="Se încarcă" /> : null}
        {error ? <StatusPanel title="Nu am putut încărca cluburile">{error}</StatusPanel> : null}
        {data?.clubs?.length ? (
          <div className="list-grid">
            {data.clubs.map((club, index) => (
              <Fragment key={club.id}>
                <ClubCard
                  club={club}
                  user={user}
                  applicationText={applicationTexts[club.id]}
                  onApplicationText={(clubId, value) => setApplicationTexts((current) => ({ ...current, [clubId]: value }))}
                  onJoin={joinClub}
                  busy={busyKey === `join-${club.id}`}
                />
                {index === 1 ? <AdSlot placement="inline" /> : null}
              </Fragment>
            ))}
          </div>
        ) : !loading && !error ? <StatusPanel title="Nu există cluburi pentru căutarea curentă" /> : null}
      </section>
    </PageShell>
  );
}

function RequestsPanel({ club, onChanged }) {
  const [requests, setRequests] = useState([]);
  const [status, setStatus] = useState("");
  const [busyKey, setBusyKey] = useState("");

  const loadRequests = useCallback(() => {
    if (!club?.id || (!club.can_manage && !club.viewer_is_site_admin)) return;
    fetchClubRequests(club.id)
      .then((data) => setRequests(data.requests || []))
      .catch((error) => setStatus(error.message || "Nu am putut încărca cererile."));
  }, [club?.id, club?.can_manage, club?.viewer_is_site_admin]);

  useEffect(() => {
    loadRequests();
  }, [loadRequests]);

  const respond = async (request, action) => {
    setStatus("");
    setBusyKey(`${request.id}-${action}`);
    try {
      await respondClubRequest(club.id, request.id, { action });
      loadRequests();
      onChanged?.();
    } catch (error) {
      setStatus(error.message || "Nu am putut răspunde cererii.");
    } finally {
      setBusyKey("");
    }
  };

  if (!club?.can_manage && !club?.viewer_is_site_admin) return null;

  return (
    <section className="club-section">
      <div className="club-section-head">
        <div>
          <h2>Cereri și invitații</h2>
          <p>{club.pending_request_count || 0} în așteptare.</p>
        </div>
      </div>
      {status ? <p className="club-status">{status}</p> : null}
      {requests.length ? (
        <div className="club-request-list">
          {requests.map((request) => (
            <article className="club-request-item" key={request.id}>
              <div>
                <strong>{usernameHandle(request.user?.username || "autor")}</strong>
                <span>{request.direction === "application" ? "cerere de aderare" : "invitație"}</span>
                {request.application_text ? <p>{request.application_text}</p> : null}
              </div>
              {club.can_manage ? (
                <div className="club-request-actions">
                  <button className="cal-btn primary" type="button" disabled={busyKey === `${request.id}-approve`} onClick={() => respond(request, "approve")}>
                    <FiCheck aria-hidden="true" />Acceptă
                  </button>
                  <button className="cal-btn" type="button" disabled={busyKey === `${request.id}-reject`} onClick={() => respond(request, "reject")}>
                    <FiX aria-hidden="true" />Respinge
                  </button>
                </div>
              ) : null}
            </article>
          ))}
        </div>
      ) : <p className="club-empty-note">Nu există cereri în așteptare.</p>}
    </section>
  );
}

function InvitePanel({ club, onChanged }) {
  const [username, setUsername] = useState("");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  if (!club?.can_manage) return null;

  const submit = async (event) => {
    event.preventDefault();
    setStatus("");
    setBusy(true);
    try {
      await inviteToClub(club.id, { username: username.trim() });
      setUsername("");
      setStatus("Invitația a fost trimisă.");
      onChanged?.();
    } catch (error) {
      setStatus(error.message || "Nu am putut trimite invitația.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="club-section">
      <div className="club-section-head">
        <div>
          <h2>Invită autori</h2>
          <p>Trimite invitații către utilizatori existenți.</p>
        </div>
      </div>
      <form className="club-inline-form" onSubmit={submit}>
        <input className="cal-input" value={username} placeholder="nume utilizator" onChange={(event) => setUsername(event.target.value)} />
        <button className="cal-btn primary" type="submit" disabled={busy || !username.trim()}>
          <FiUserPlus aria-hidden="true" />Invită
        </button>
      </form>
      {status ? <p className="club-status">{status}</p> : null}
    </section>
  );
}

function MediaPanel({ club, onChanged }) {
  const [busyKey, setBusyKey] = useState("");
  const [status, setStatus] = useState("");

  if (!club?.can_upload_media) return null;

  const upload = async (kind, file) => {
    if (!file) return;
    setStatus("");
    setBusyKey(`upload-${kind}`);
    try {
      await uploadClubMedia(club.id, kind, file);
      onChanged?.();
    } catch (error) {
      setStatus(error.message || "Nu am putut încărca imaginea.");
    } finally {
      setBusyKey("");
    }
  };

  const remove = async (kind) => {
    setStatus("");
    setBusyKey(`delete-${kind}`);
    try {
      await deleteClubMedia(club.id, kind);
      onChanged?.();
    } catch (error) {
      setStatus(error.message || "Nu am putut șterge imaginea.");
    } finally {
      setBusyKey("");
    }
  };

  return (
    <section className="club-section">
      <div className="club-section-head">
        <div>
          <h2>Imagini club</h2>
          <p>Disponibil pentru Cronicar și Rapsod.</p>
        </div>
      </div>
      <div className="club-media-actions">
        {[
          ["profil", "Imagine profil", club.has_profile_photo],
          ["coperta", "Copertă", club.has_cover_photo]
        ].map(([kind, label, hasImage]) => (
          <div className="club-media-control" key={kind}>
            <span><FiImage aria-hidden="true" />{label}</span>
            <label className="cal-btn">
              <FiUpload aria-hidden="true" />Încarcă
              <input type="file" accept="image/png,image/jpeg,image/webp,image/avif" disabled={busyKey === `upload-${kind}`} onChange={(event) => upload(kind, event.target.files?.[0])} />
            </label>
            {hasImage ? (
              <button className="cal-btn" type="button" disabled={busyKey === `delete-${kind}`} onClick={() => remove(kind)}>
                <FiTrash2 aria-hidden="true" />Șterge
              </button>
            ) : null}
          </div>
        ))}
      </div>
      {status ? <p className="club-status">{status}</p> : null}
    </section>
  );
}

function BoardPanel({ club, user, reloadClub }) {
  const [messages, setMessages] = useState(club.recent_messages || []);
  const [threadForm, setThreadForm] = useState({ title: "", content: "" });
  const [composerOpen, setComposerOpen] = useState(true);
  const [replyForms, setReplyForms] = useState({});
  const [status, setStatus] = useState("");
  const [busyKey, setBusyKey] = useState("");
  const canPost = Boolean(club.can_post || club.my_role);

  const loadBoard = useCallback(() => {
    if (!club?.id) return;
    fetchClubBoard(club.id)
      .then((data) => setMessages(data.messages || []))
      .catch((error) => setStatus(error.message || "Nu am putut încărca discuțiile."));
  }, [club?.id]);

  useEffect(() => {
    setMessages(club.recent_messages || []);
    loadBoard();
  }, [club?.id, club?.recent_messages, loadBoard]);

  const createThread = async (event) => {
    event.preventDefault();
    setStatus("");
    setBusyKey("thread");
    try {
      await createClubBoardMessage(club.id, {
        title: threadForm.title.trim(),
        content: threadForm.content.trim()
      });
      setThreadForm({ title: "", content: "" });
      loadBoard();
      reloadClub?.();
    } catch (error) {
      setStatus(error.message || "Nu am putut publica firul.");
    } finally {
      setBusyKey("");
    }
  };

  const createReply = async (message) => {
    const content = (replyForms[message.id] || "").trim();
    if (!content) return;
    setStatus("");
    setBusyKey(`reply-${message.id}`);
    try {
      await createClubBoardMessage(club.id, { parent_id: message.id, content });
      setReplyForms((current) => ({ ...current, [message.id]: "" }));
      loadBoard();
      reloadClub?.();
    } catch (error) {
      setStatus(error.message || "Nu am putut publica răspunsul.");
    } finally {
      setBusyKey("");
    }
  };

  const removeMessage = async (message) => {
    setStatus("");
    setBusyKey(`delete-${message.id}`);
    try {
      await deleteClubBoardMessage(club.id, message.id);
      loadBoard();
      reloadClub?.();
    } catch (error) {
      setStatus(error.message || "Nu am putut șterge mesajul.");
    } finally {
      setBusyKey("");
    }
  };

  const canDelete = (message) => (
    user?.id === message.author?.id || club.can_manage || user?.is_admin
  );

  return (
    <section className="club-section" id="tabla">
      <div className="club-section-head">
        <div>
          <h2>Discutii club</h2>
          <p>Fire de atelier și răspunsuri între membri.</p>
        </div>
        {canPost ? (
          <button
            className="cal-btn primary"
            type="button"
            aria-expanded={composerOpen}
            aria-controls="club-thread-form"
            onClick={() => setComposerOpen((open) => !open)}
          >
            {composerOpen ? <FiX aria-hidden="true" /> : <FiPlus aria-hidden="true" />}
            {composerOpen ? "Închide formularul" : "Discuție nouă"}
          </button>
        ) : null}
      </div>
      {canPost && composerOpen ? (
        <form id="club-thread-form" className="club-thread-form" onSubmit={createThread}>
          <input className="cal-input" value={threadForm.title} placeholder="Titlul firului" maxLength={160} onChange={(event) => setThreadForm((current) => ({ ...current, title: event.target.value }))} />
          <textarea className="cal-textarea compact" value={threadForm.content} placeholder="Mesajul de deschidere" onChange={(event) => setThreadForm((current) => ({ ...current, content: event.target.value }))} />
          <button className="cal-btn primary" type="submit" disabled={busyKey === "thread" || !threadForm.title.trim() || !threadForm.content.trim()}>
            <FiPlus aria-hidden="true" />Deschide discuție
          </button>
        </form>
      ) : !canPost ? (
        <StatusPanel title="Mod citire">Administratorii site-ului pot citi și modera discuțiile, dar pot posta doar ca membri ai clubului.</StatusPanel>
      ) : null}
      {status ? <p className="club-status">{status}</p> : null}
      <div className="club-board-list">
        {messages.map((message) => (
          <article className="club-thread" id={`club-message-${message.id}`} key={message.id}>
            <div className="club-message-head">
              <div>
                <h3>{message.title || "Fir fără titlu"}</h3>
                <span>{message.author?.username ? usernameHandle(message.author.username) : "autor"} · {formatDateTime(message.created_at)}</span>
              </div>
              {canDelete(message) ? (
                <button className="cal-btn" type="button" disabled={busyKey === `delete-${message.id}`} onClick={() => removeMessage(message)}>
                  <FiTrash2 aria-hidden="true" />Șterge
                </button>
              ) : null}
            </div>
            <p>{message.content}</p>
            {message.replies?.length ? (
              <div className="club-replies">
                {message.replies.map((reply) => (
                  <div className="club-reply" id={`club-message-${reply.id}`} key={reply.id}>
                    <div className="club-message-head compact">
                      <span>{reply.author?.username ? usernameHandle(reply.author.username) : "autor"} · {formatDateTime(reply.created_at)}</span>
                      {canDelete(reply) ? (
                        <button className="cal-btn" type="button" disabled={busyKey === `delete-${reply.id}`} onClick={() => removeMessage(reply)}>
                          <FiTrash2 aria-hidden="true" />Șterge
                        </button>
                      ) : null}
                    </div>
                    <p>{reply.content}</p>
                  </div>
                ))}
              </div>
            ) : null}
            {canPost ? (
              <div className="club-reply-form">
                <textarea className="cal-textarea compact" value={replyForms[message.id] || ""} placeholder="Răspunde în fir" onChange={(event) => setReplyForms((current) => ({ ...current, [message.id]: event.target.value }))} />
                <button className="cal-btn" type="button" disabled={busyKey === `reply-${message.id}` || !(replyForms[message.id] || "").trim()} onClick={() => createReply(message)}>
                  <FiSend aria-hidden="true" />Răspunde
                </button>
              </div>
            ) : null}
          </article>
        ))}
      </div>
      {!messages.length ? <p className="club-empty-note">Încă nu există discuții în club.</p> : null}
    </section>
  );
}

function ClubDetailView({ slug, user }) {
  const [reloadKey, setReloadKey] = useState(0);
  const { data, error, loading } = useAsync(() => fetchClub(slug), [slug, reloadKey]);
  const reloadClub = () => setReloadKey((value) => value + 1);
  const coverStyle = useMemo(() => {
    if (!data) return undefined;
    const fallbackSeed = `${data.slug || data.title || "club"}-cover-sky`;
    const url = data.cover_photo_url || data.cover_url || coverPreviewUrl(fallbackSeed);
    return { backgroundImage: `url(${url})` };
  }, [data]);

  return (
    <PageShell kicker="club" title={data?.title ?? "Club"} sub={data?.motto || data?.description}>
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca clubul">{error}</StatusPanel> : null}
      {data ? (
        <div className="detail-stack club-detail">
          <section className={`club-hero with-cover ${ownerTierClass(data)}`} style={coverStyle}>
            <div className="club-hero-content">
              <ClubAvatar club={data} size="large" />
              <div>
                <p className="piece-card-kicker">{categoryLabel(data.speciality)} · {JOIN_POLICY_LABELS[data.join_policy]}</p>
                <h2>{data.title}</h2>
                {data.theme ? <p>Tema: {data.theme}</p> : null}
              </div>
            </div>
          </section>

          <div className="rail">
            <div className="rail-stat">
              <span className="rail-label">Membri</span>
              <span className="rail-count">{data.member_count}</span>
              <span className="rail-sub">{categoryLabel(data.speciality)}</span>
            </div>
            <div className="rail-stat">
              <span className="rail-label">Înscriere</span>
              <span className="rail-count compact">{JOIN_POLICY_LABELS[data.join_policy]}</span>
              <span className="rail-sub">Mod de intrare</span>
            </div>
          </div>

          <BoardPanel club={data} user={user} reloadClub={reloadClub} />

          <MediaPanel club={data} onChanged={reloadClub} />
          <InvitePanel club={data} onChanged={reloadClub} />
          <RequestsPanel club={data} onChanged={reloadClub} />

          {data.achievements?.length ? (
            <section className="club-section">
              <div className="club-section-head">
                <div>
                  <h2>Insigne</h2>
                  <p>Realizări de atelier deblocate automat.</p>
                </div>
              </div>
              <div className="club-achievement-list">
                {data.achievements.map((achievement) => (
                  <ClubAchievementCard achievement={achievement} key={achievement.key} />
                ))}
              </div>
            </section>
          ) : null}

          {data.featured ? (
            <section className="club-section">
              <div className="club-section-head">
                <div>
                  <h2>Creația săptămânii</h2>
                  <p>{data.featured.post_author?.username ? usernameHandle(data.featured.post_author.username) : "autor"}</p>
                </div>
                <a className="cal-btn primary" href={data.featured.post_author?.username ? `${blogUrl(data.featured.post_author.username)}/${data.featured.post_slug}` : "#"}>
                  Citește
                </a>
              </div>
              <p className="club-featured-title">{data.featured.post_title}</p>
              {data.can_manage ? (
                <button className="cal-btn" type="button" onClick={() => clearClubFeatured(data.id).then(reloadClub)}>
                  <FiX aria-hidden="true" />Scoate recomandarea
                </button>
              ) : null}
            </section>
          ) : null}

          {data.members?.length ? (
            <section className="club-section">
              <div className="club-section-head">
                <div>
                  <h2>Membri</h2>
                  <p>Autorii din spațiul de lucru.</p>
                </div>
              </div>
              <div className="list-grid compact">
                {data.members.map((member) => (
                  <a className="piece-card" key={member.id} href={blogUrl(member.username)}>
                    <div className="piece-card-kicker">{roleLabel(member.role)}</div>
                    <h2 className="piece-card-title">{usernameHandle(member.username)}</h2>
                    <p className="piece-card-excerpt">{member.contribution_count} contribuții</p>
                  </a>
                ))}
              </div>
            </section>
          ) : null}
        </div>
      ) : null}
    </PageShell>
  );
}

export default function ClubsRoute({ route, user }) {
  if (route.name === "club") return <ClubDetailView slug={route.slug} user={user} />;
  return <ClubsView user={user} />;
}
