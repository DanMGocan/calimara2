import { Fragment, useCallback, useEffect, useState } from "react";
import { FiChevronDown, FiChevronRight, FiTrash2 } from "react-icons/fi";
import { addDiacritics } from "../api/writing.js";
import {
  applyToTheatrePlay,
  assignTheatreCharacter,
  createTheatreCharacter,
  createTheatrePlay,
  createTheatreReply,
  createTheatreStageDirection,
  deleteTheatreCharacter,
  endTheatreScene,
  fetchTheatrePlay,
  fetchTheatrePlays,
  fetchMyTheatreInvitations,
  fetchTheatreRequests,
  inviteToTheatrePlay,
  overrideTheatreTurn,
  respondTheatreRequest,
  reviewTheatreCharacter,
  startTheatreScene,
  theatrePdfUrl
} from "../api/theatre.js";
import { searchUsers } from "../api/users.js";
import { AuthorLink, RichTextContent } from "../app/content.jsx";
import { DiacriticsControl, DiacriticsProgressOverlay, DiacriticsReviewPanel, diacriticsSubmitLabel, useDiacriticsProgress, useDiacriticsQuota } from "../app/diacritics.jsx";
import { formatDateTime, usernameHandle } from "../app/format.js";
import { useAsync } from "../app/hooks.js";
import { AuthRequired, PageShell, StatusPanel } from "../app/layout.jsx";
import { mainPath } from "../app/paths.js";
import { RichTextEditor } from "../app/editor.jsx";
import { theatrePlaySeo, usePageSeo } from "../app/seo.js";

const EMPTY_CHARACTER = { name: "", description: "", assigned_username: "" };
const CHARACTER_INVITE_HELPER = "Invită un utilizator să joace acest personaj sau lasă rolul liber. Utilizatorii pot aplica să îl joace.";

function statusLabel(value) {
  return {
    setup: "pregătire",
    active: "activă",
    completed: "încheiată",
    pending: "în moderare",
    approved: "aprobat",
    flagged: "în revizie",
    rejected: "respins",
    invitation: "invitație",
    application: "cerere"
  }[value] || value || "";
}

function assignmentStatus(character) {
  if (character?.assigned_user_id) return "personaj_atribuit";
  return character?.assignment_status || "liber";
}

function assignmentStatusLabel(value) {
  return {
    liber: "liber",
    utilizator_invitat: "utilizator invitat",
    personaj_atribuit: "personaj atribuit"
  }[value] || value || "liber";
}

function entryTypeLabel(value) {
  return {
    scene_opening: "Deschidere",
    line: "Replică",
    stage_direction: "Indicație scenică",
    scene_end: "Încheiere"
  }[value] || "Text";
}

function availableCharacters(play) {
  return (play?.characters || []).filter((character) => character.status === "approved" && assignmentStatus(character) === "liber");
}

function readyCharacters(play) {
  return (play?.characters || []).filter((character) => character.status === "approved" && character.assigned_user_id);
}

function TheatreHelpModal({ open, onClose }) {
  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (event) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="access-modal-scrim" role="presentation" onClick={onClose}>
      <section className="access-modal theatre-help-modal" role="dialog" aria-modal="true" aria-labelledby="theatre-help-title" onClick={(event) => event.stopPropagation()}>
        <button className="access-modal-close" type="button" aria-label="Închide" onClick={onClose}>x</button>
        <h2 id="theatre-help-title" className="access-modal-title">Cum funcționează Teatrul colaborativ</h2>
        <div className="access-modal-body theatre-help-body">
          <p>Teatrul colaborativ este o piesă scrisă pe rând, cu personaje atribuite unor utilizatori.</p>
          <ul className="theatre-help-list">
            <li>Creatorul pornește piesa și definește distribuția inițială.</li>
            <li>Utilizatorii autentificați pot cere un rol sau pot fi invitați de creator.</li>
            <li>Creatorul aprobă personajele și atribuie roluri; un utilizator joacă un singur personaj într-o piesă.</li>
            <li>Când începe o scenă, rândul de scriere trece de la un personaj la următorul ales.</li>
            <li>Creatorul poate adăuga indicații scenice, schimba rândul și încheia scenele.</li>
            <li>Piesa rămâne publică live, iar conținutul trece prin moderarea obișnuită.</li>
          </ul>
        </div>
      </section>
    </div>
  );
}

function TheatreListView({ user }) {
  const [helpOpen, setHelpOpen] = useState(false);
  const [handledInvitationIds, setHandledInvitationIds] = useState(() => new Set());
  const [invitationBusy, setInvitationBusy] = useState("");
  const [invitationError, setInvitationError] = useState("");
  const { data, error, loading } = useAsync(fetchTheatrePlays, []);
  const {
    data: invitationsData,
    error: invitationsError,
    loading: invitationsLoading
  } = useAsync(() => user ? fetchMyTheatreInvitations() : Promise.resolve({ items: [] }), [user?.id]);
  useEffect(() => {
    setHandledInvitationIds(new Set());
  }, [user?.id]);
  const invitationItems = (invitationsData?.items || []).filter((item) => !handledInvitationIds.has(item.request.id));
  const respondToInvitation = async (item, action) => {
    if (invitationBusy) return;
    setInvitationBusy(`${item.request.id}:${action}`);
    setInvitationError("");
    try {
      await respondTheatreRequest(item.play.id, item.request.id, { action });
      setHandledInvitationIds((current) => new Set([...current, item.request.id]));
    } catch (requestError) {
      setInvitationError(requestError.message || "Nu am putut răspunde invitației.");
    } finally {
      setInvitationBusy("");
    }
  };
  return (
    <PageShell
      kicker="teatru"
      title="Teatru colaborativ"
      sub="Piese scrise pe rând, cu personaje atribuite și scene publice live."
      titleAction={(
        <div className="theatre-title-actions">
          <button
            className="cal-btn theatre-help-title-action"
            type="button"
            aria-label="Cum funcționează Teatrul colaborativ"
            title="Cum funcționează Teatrul colaborativ"
            onClick={() => setHelpOpen(true)}
          >
            ?
          </button>
          {user ? <a className="cal-btn primary theatre-create-title-action" href={mainPath("/teatru/nou")}>Creează piesă</a> : null}
        </div>
      )}
    >
      <TheatreHelpModal open={helpOpen} onClose={() => setHelpOpen(false)} />
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca piesele">{error.message || String(error)}</StatusPanel> : null}
      {user && invitationsLoading ? <StatusPanel title="Se verifică invitațiile" /> : null}
      {user && invitationsError ? <StatusPanel title="Nu am putut încărca invitațiile">{invitationsError.message || String(invitationsError)}</StatusPanel> : null}
      {user && invitationItems.length ? (
        <section className="theatre-panel wide theatre-invitations-panel">
          <h2>Invitațiile tale</h2>
          <div className="theatre-request-list">
            {invitationItems.map((item) => (
              <article className="theatre-request" key={item.request.id}>
                <div>
                  <strong>{item.play.title}</strong>
                  <span>{item.request.character?.name || "personaj fără nume"}</span>
                </div>
                <div className="theatre-inline-actions">
                  <a className="cal-btn" href={mainPath(`/teatru/${item.play.slug}`)}>Deschide</a>
                  <button className="cal-btn primary" type="button" disabled={Boolean(invitationBusy)} onClick={() => respondToInvitation(item, "approve")}>Acceptă</button>
                  <button className="cal-btn danger" type="button" disabled={Boolean(invitationBusy)} onClick={() => respondToInvitation(item, "reject")}>Refuză</button>
                </div>
              </article>
            ))}
          </div>
          {invitationError ? <div className="inline-error">{invitationError}</div> : null}
        </section>
      ) : null}
      {data?.plays?.length ? (
        <div className="list-grid theatre-list">
          {data.plays.map((play, index) => (
            <Fragment key={play.id}>
              <article className="piece-card theatre-card">
                <div className="piece-card-kicker">{statusLabel(play.status)}</div>
                <h2 className="piece-card-title">
                  <a className="post-title-link" href={mainPath(`/teatru/${play.slug}`)}>{play.title}</a>
                </h2>
                <p className="piece-card-excerpt">{play.description || "Piesă colaborativă pe călimara.ro."}</p>
                <div className="piece-card-meta">
                  <span>{play.character_count} personaje</span>
                  <span>{play.scene_count} scene</span>
                  {play.creator ? <AuthorLink user={play.creator} /> : null}
                </div>
              </article>
              {index === 1 ? <div className="theatre-list-break" aria-hidden="true" /> : null}
            </Fragment>
          ))}
        </div>
      ) : !loading && !error ? <StatusPanel title="Nu există piese încă" /> : null}
    </PageShell>
  );
}

function UserSearchInput({ id, value, onChange, label, placeholder, helper, disabled = false }) {
  const [state, setState] = useState({ results: [], loading: false, error: "" });

  useEffect(() => {
    const term = value.trim();
    if (disabled || term.length < 3) {
      setState({ results: [], loading: false, error: "" });
      return undefined;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      setState((current) => ({ ...current, loading: true, error: "" }));
      searchUsers(term)
        .then((results) => {
          if (!cancelled) setState({ results: Array.isArray(results) ? results : [], loading: false, error: "" });
        })
        .catch((requestError) => {
          if (!cancelled) setState({ results: [], loading: false, error: requestError.message || "Nu am putut căuta utilizatori." });
        });
    }, 220);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [value, disabled]);

  return (
    <div className="theatre-user-search">
      {label ? <label className="cal-label" htmlFor={id}>{label}</label> : null}
      <input
        id={id}
        className="cal-input"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder || label}
        minLength="3"
        maxLength="255"
        disabled={disabled}
      />
      {helper ? <p className="theatre-field-hint">{helper}</p> : null}
      {state.loading ? <div className="theatre-suggestions-note">Se caută utilizatori...</div> : null}
      {state.error ? <div className="inline-error">{state.error}</div> : null}
      {!state.loading && state.results.length ? (
        <div className="theatre-user-suggestions">
          {state.results.map((result) => (
            <button
              className="theatre-user-suggestion"
              type="button"
              key={result.id}
              onClick={() => onChange(result.username)}
            >
              <strong>{usernameHandle(result.username)}</strong>
              {result.subtitle ? <span>{result.subtitle}</span> : null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function TheatreCreateView({ user }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [characterDraft, setCharacterDraft] = useState({ ...EMPTY_CHARACTER });
  const [characters, setCharacters] = useState([]);
  const [editingCharacterIndex, setEditingCharacterIndex] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [directSubmitting, setDirectSubmitting] = useState(false);
  const [autoDiacritics, setAutoDiacritics] = useState(false);
  const [diacriticsReview, setDiacriticsReview] = useState(null);
  const [error, setError] = useState("");
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

  if (!user) return <AuthRequired />;

  const resetDiacriticsReview = () => {
    if (diacriticsReview) setDiacriticsReview(null);
  };

  const updateDraft = (field, value) => {
    setCharacterDraft((current) => ({ ...current, [field]: value }));
    resetDiacriticsReview();
  };

  const updateAddedCharacter = (index, field, value) => {
    setCharacters((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, [field]: value } : item));
    resetDiacriticsReview();
  };

  const cleanCharacter = (character) => ({
    name: character.name.trim(),
    description: character.description.trim(),
    assigned_username: (character.assigned_username || "").trim() || undefined
  });

  const draftHasContent = Boolean(characterDraft.name.trim() || characterDraft.description.trim() || characterDraft.assigned_username.trim());

  const addCharacter = () => {
    const clean = cleanCharacter(characterDraft);
    if (!clean.name || !clean.description) {
      setError("Completează numele și descrierea personajului înainte să îl adaugi în listă.");
      return;
    }
    setCharacters((current) => [...current, clean]);
    setCharacterDraft({ ...EMPTY_CHARACTER });
    setEditingCharacterIndex(null);
    setError("");
    resetDiacriticsReview();
  };

  const removeCharacter = (index) => {
    setCharacters((current) => current.filter((_, itemIndex) => itemIndex !== index));
    setEditingCharacterIndex((current) => {
      if (current === null) return null;
      if (current === index) return null;
      return current > index ? current - 1 : current;
    });
    resetDiacriticsReview();
  };

  const submitPlay = async ({ skipDiacritics = false } = {}) => {
    if (submitting) return;
    const cleanCharacters = characters.map(cleanCharacter).filter((character) => character.name && character.description);
    if (draftHasContent) {
      setError("Adaugă personajul început în listă înainte de pasul următor.");
      return;
    }
    if (!title.trim()) {
      setError("Titlul este obligatoriu.");
      return;
    }
    setSubmitting(true);
    setDirectSubmitting(skipDiacritics);
    setError("");
    try {
      if (!skipDiacritics && user && autoDiacritics && !diacriticsReview) {
        startDiacriticsProgress({
          title,
          content: [description, ...cleanCharacters.map((character) => character.description)].join("\n\n")
        });
        const converted = await addDiacritics({
          kind: "theatre_play",
          title,
          description,
          characters: cleanCharacters.map((character, index) => ({
            index,
            description: character.description
          }))
        });
        finishDiacriticsProgress();
        applyDiacriticsQuota(converted.quota);
        const convertedDescriptions = new Map((converted.characters || []).map((item) => [item.index, item.description]));
        setTitle(converted.title ?? title);
        setDescription(converted.description ?? description);
        setCharacters((current) => current.map((character, index) => ({
          ...character,
          description: convertedDescriptions.get(index) ?? character.description
        })));
        setDiacriticsReview({
          originalTitle: title,
          originalDescription: description,
          originalCharacters: characters.map((character) => ({ ...character })),
          changed: converted.changed
        });
        setSubmitting(false);
        setDirectSubmitting(false);
        return;
      }
      const created = await createTheatrePlay({
        title: title.trim(),
        description: description.trim() || undefined,
        characters: cleanCharacters
      });
      window.location.href = mainPath(`/teatru/${created.slug}`);
    } catch (requestError) {
      failDiacriticsProgress();
      setError(requestError.message || "Nu am putut crea piesa.");
      setSubmitting(false);
      setDirectSubmitting(false);
    }
  };

  const submit = async (event) => {
    event.preventDefault();
    await submitPlay();
  };
  const canContinueDirectly = Boolean(user && autoDiacritics && !diacriticsReview);

  return (
    <PageShell kicker="teatru" title="Piesă nouă" sub="Definește distribuția inițială și invită actori dacă vrei.">
      <DiacriticsProgressOverlay {...diacriticsProgress} />
      <form className="theatre-form theatre-create-form" onSubmit={submit}>
        <label className="cal-label" htmlFor="theatre-title">Titlu</label>
        <input id="theatre-title" className="cal-input" value={title} onChange={(event) => {
          setTitle(event.target.value);
          resetDiacriticsReview();
        }} maxLength={160} required />
        <label className="cal-label" htmlFor="theatre-description">Descriere</label>
        <textarea id="theatre-description" className="cal-textarea" value={description} onChange={(event) => {
          setDescription(event.target.value);
          resetDiacriticsReview();
        }} maxLength={3000} rows={4} />
        <p className="theatre-create-note">Scenele și descrierea scenelor sunt setate pe ecranul următor.</p>
        <section className="theatre-panel theatre-character-add">
          <h2>Adaugă personaj</h2>
          <input className="cal-input" value={characterDraft.name} onChange={(event) => updateDraft("name", event.target.value)} placeholder="Nume personaj" maxLength={120} />
          <textarea className="cal-textarea" value={characterDraft.description} onChange={(event) => updateDraft("description", event.target.value)} placeholder="Descriere personaj" maxLength={2500} rows={3} />
          <UserSearchInput
            id="theatre-character-invite"
            value={characterDraft.assigned_username}
            onChange={(value) => updateDraft("assigned_username", value)}
            label="Invită un utilizator să joace acest personaj"
            helper={CHARACTER_INVITE_HELPER}
          />
          <button className="cal-btn" type="button" onClick={addCharacter}>Adaugă personaj în listă</button>
        </section>
        <section className="theatre-panel theatre-character-list-panel">
          <h2>Personaje adăugate</h2>
          {characters.length ? (
            <div className="theatre-character-list">
              {characters.map((character, index) => {
                const isEditing = editingCharacterIndex === index;
                const editorId = `theatre-character-editor-${index}`;
                const characterLabel = character.name || "personajul";
                return (
                  <article className={`theatre-character-summary ${isEditing ? "is-editing" : ""}`} key={`character-${index}`}>
                    <div className="theatre-character-summary-row">
                      <button
                        className="theatre-character-toggle"
                        type="button"
                        onClick={() => setEditingCharacterIndex(isEditing ? null : index)}
                        aria-label={isEditing ? `Ascunde editarea pentru ${characterLabel}` : `Editează ${characterLabel}`}
                        aria-expanded={isEditing}
                        aria-controls={editorId}
                        title={isEditing ? "Ascunde editarea" : "Editează"}
                      >
                        {isEditing ? <FiChevronDown aria-hidden="true" /> : <FiChevronRight aria-hidden="true" />}
                      </button>
                      <div className="theatre-character-summary-main">
                        <strong>{character.name || "Personaj fără nume"}</strong>
                        <p>{character.description || "Fără descriere."}</p>
                      </div>
                      <div className="theatre-character-summary-meta">
                        {character.assigned_username ? <span>{usernameHandle(character.assigned_username)}</span> : null}
                        <button
                          className="theatre-character-remove"
                          type="button"
                          onClick={() => removeCharacter(index)}
                          aria-label={`Șterge ${characterLabel}`}
                          title="Șterge"
                        >
                          <FiTrash2 aria-hidden="true" />
                        </button>
                      </div>
                    </div>
                    {isEditing ? (
                      <div className="theatre-character-edit-fields" id={editorId}>
                        <input className="cal-input" value={character.name} onChange={(event) => updateAddedCharacter(index, "name", event.target.value)} placeholder="Nume personaj" maxLength={120} />
                        <textarea className="cal-textarea" value={character.description} onChange={(event) => updateAddedCharacter(index, "description", event.target.value)} placeholder="Descriere personaj" maxLength={2500} rows={3} />
                        <UserSearchInput
                          id={`theatre-character-invite-${index}`}
                          value={character.assigned_username || ""}
                          onChange={(value) => updateAddedCharacter(index, "assigned_username", value)}
                          label="Invită un utilizator să joace acest personaj"
                          helper={CHARACTER_INVITE_HELPER}
                        />
                      </div>
                    ) : null}
                  </article>
                );
              })}
            </div>
          ) : <p className="muted">Nu ai adăugat personaje încă.</p>}
        </section>
        <div className="theatre-create-submit-row">
          <DiacriticsReviewPanel
            active={Boolean(diacriticsReview)}
            changed={Boolean(diacriticsReview?.changed)}
            onReset={diacriticsReview ? () => {
              setTitle(diacriticsReview.originalTitle);
              setDescription(diacriticsReview.originalDescription);
              setCharacters(diacriticsReview.originalCharacters);
              setEditingCharacterIndex(null);
              setDiacriticsReview(null);
            } : null}
          />
        </div>
        <div className="theatre-form-actions">
          <DiacriticsControl
            user={user}
            enabled={autoDiacritics}
            disabled={Boolean(diacriticsReview)}
            label="Adaugă diacritice"
            quota={diacriticsQuota}
            quotaLoading={diacriticsQuotaLoading}
            quotaError={diacriticsQuotaError}
            onChange={(checked) => {
              setAutoDiacritics(checked);
              setDiacriticsReview(null);
            }}
          />
          <button className="cal-btn primary" type="submit" disabled={submitting || !title.trim()}>
            {diacriticsSubmitLabel({
              submitting,
              reviewing: Boolean(diacriticsReview),
              enabled: Boolean(user && autoDiacritics && !directSubmitting),
              submitLabel: "Pasul următor"
            })}
          </button>
          {canContinueDirectly ? (
            <button className="cal-btn" type="button" onClick={() => submitPlay({ skipDiacritics: true })} disabled={submitting || !title.trim()}>
              {directSubmitting ? "Se creează..." : "Pasul următor fără Diacritice"}
            </button>
          ) : null}
          {error ? <span className="inline-error">{error}</span> : null}
        </div>
      </form>
    </PageShell>
  );
}

function RequestPanel({ play, requests, onRespond, busyId }) {
  const pendingCharacters = (play.characters || []).filter((character) => character.status === "pending");
  return (
    <section className="theatre-panel">
      <h2>Cereri și personaje propuse</h2>
      {requests.length ? (
        <div className="theatre-request-list">
          {requests.map((request) => (
            <div className="theatre-request" key={request.id}>
              <div>
                <strong>{usernameHandle(request.user?.username)}</strong>
                <span>{statusLabel(request.direction)}{request.character ? ` · ${request.character.name}` : ""}</span>
                {request.note ? <p>{request.note}</p> : null}
              </div>
              <div className="theatre-inline-actions">
                <button className="cal-btn primary" type="button" disabled={busyId === request.id} onClick={() => onRespond(request.id, "approve")}>Acceptă</button>
                <button className="cal-btn danger" type="button" disabled={busyId === request.id} onClick={() => onRespond(request.id, "reject")}>Respinge</button>
              </div>
            </div>
          ))}
        </div>
      ) : <p className="muted">Nu există cereri în așteptare.</p>}
      {pendingCharacters.length ? (
        <div className="theatre-request-list">
          {pendingCharacters.map((character) => (
            <div className="theatre-request" key={character.id}>
              <div>
                <strong>{character.name}</strong>
                <span>propus de {usernameHandle(character.proposer?.username)}</span>
                <p>{character.description}</p>
              </div>
              <div className="theatre-inline-actions">
                <button className="cal-btn primary" type="button" onClick={() => onRespond(`character:${character.id}`, "approve")}>Aprobă</button>
                <button className="cal-btn danger" type="button" onClick={() => onRespond(`character:${character.id}`, "reject")}>Respinge</button>
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function CreatorConsole({ play, requests, onRefresh }) {
  const activeScene = (play.scenes || []).find((scene) => scene.id === play.current_scene_id && scene.status === "active");
  const [sceneTitle, setSceneTitle] = useState("");
  const [sceneOpening, setSceneOpening] = useState("");
  const [firstCharacterId, setFirstCharacterId] = useState("");
  const [direction, setDirection] = useState("");
  const [overrideCharacterId, setOverrideCharacterId] = useState("");
  const [overrideNote, setOverrideNote] = useState("");
  const [endNote, setEndNote] = useState("");
  const [characterActions, setCharacterActions] = useState({});
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const assignedCharacters = readyCharacters(play);
  const approvedCharacters = (play.characters || []).filter((character) => character.status === "approved");

  const run = async (key, action) => {
    if (busy) return;
    setBusy(key);
    setError("");
    try {
      await action();
      await onRefresh();
    } catch (requestError) {
      setError(requestError.message || "Acțiunea a eșuat.");
    } finally {
      setBusy("");
    }
  };

  const respond = (id, action) => {
    if (String(id).startsWith("character:")) {
      const characterId = String(id).slice("character:".length);
      return run(`character:${characterId}`, () => reviewTheatreCharacter(play.id, characterId, { action }));
    }
    return run(`request:${id}`, () => respondTheatreRequest(play.id, id, { action }));
  };

  const setCharacterUsername = (characterId, value) => {
    setCharacterActions((current) => ({ ...current, [characterId]: value }));
  };

  const clearCharacterUsername = (characterId) => {
    setCharacterActions((current) => ({ ...current, [characterId]: "" }));
  };

  return (
    <div className="theatre-console-grid">
      <RequestPanel play={play} requests={requests} onRespond={respond} busyId={busy} />
      <section className="theatre-panel wide">
        <h2>Personaje</h2>
        {approvedCharacters.length ? (
          <div className="theatre-character-playlist">
            {approvedCharacters.map((character) => {
              const status = assignmentStatus(character);
              const username = characterActions[character.id] || "";
              return (
                <article className={`theatre-character-playlist-row ${status}`} key={character.id}>
                  <div className="theatre-character-playlist-main">
                    <div className="theatre-cast-head">
                      <strong>{character.name}</strong>
                      <span>{assignmentStatusLabel(status)}</span>
                    </div>
                    <p>{character.description}</p>
                    <div className="theatre-cast-meta">
                      {character.assigned_user ? <span>{usernameHandle(character.assigned_user.username)}</span> : null}
                      {!character.assigned_user && character.pending_invitation_user ? <span>invitat: {usernameHandle(character.pending_invitation_user.username)}</span> : null}
                    </div>
                  </div>
                  {status === "liber" ? (
                    <div className="theatre-character-playlist-actions">
                      <UserSearchInput
                        id={`theatre-playlist-user-${character.id}`}
                        value={username}
                        onChange={(value) => setCharacterUsername(character.id, value)}
                        label="Invită un utilizator să joace acest personaj"
                      />
                      <div className="theatre-inline-actions">
                        <button className="cal-btn primary" type="button" disabled={!username.trim() || busy === `invite:${character.id}`} onClick={() => run(`invite:${character.id}`, async () => {
                          await inviteToTheatrePlay(play.id, { username, character_id: character.id });
                          clearCharacterUsername(character.id);
                        })}>Invită</button>
                        <button className="cal-btn" type="button" disabled={!username.trim() || busy === `assign:${character.id}`} onClick={() => run(`assign:${character.id}`, async () => {
                          await assignTheatreCharacter(play.id, character.id, { username });
                          clearCharacterUsername(character.id);
                        })}>Atribuie</button>
                      </div>
                    </div>
                  ) : null}
                  <button className="cal-btn danger" type="button" disabled={busy === `delete:${character.id}`} onClick={() => run(`delete:${character.id}`, () => deleteTheatreCharacter(play.id, character.id))}>Șterge</button>
                </article>
              );
            })}
          </div>
        ) : <p className="muted">Nu există personaje aprobate încă.</p>}
      </section>
      <section className="theatre-panel wide">
        <h2>{activeScene ? "Scena activă" : "Pornește scena"}</h2>
        {!activeScene ? (
          <div className="theatre-form">
            <label className="cal-label" htmlFor="theatre-scene-title">Numărul actului</label>
            <input id="theatre-scene-title" className="cal-input" value={sceneTitle} onChange={(event) => setSceneTitle(event.target.value)} placeholder="Actul 1, de exemplu" />
            <label className="cal-label" htmlFor="theatre-first-character">Primul personaj</label>
            <select id="theatre-first-character" className="cal-input" value={firstCharacterId} onChange={(event) => setFirstCharacterId(event.target.value)}>
              <option value="">Primul personaj</option>
              {assignedCharacters.map((character) => <option value={character.id} key={character.id}>{character.name} · {character.assigned_user?.username}</option>)}
            </select>
            <label className="cal-label" htmlFor="theatre-scene-opening">Descriere scenă</label>
            <RichTextEditor id="theatre-scene-opening" value={sceneOpening} onChange={setSceneOpening} maxLength={8000} mentionSearch={searchUsers} />
            <button className="cal-btn primary" type="button" disabled={!sceneTitle.trim() || !firstCharacterId || !sceneOpening} onClick={() => run("scene", async () => {
              await startTheatreScene(play.id, { title: sceneTitle, first_character_id: Number(firstCharacterId), content: sceneOpening });
              setSceneTitle("");
              setFirstCharacterId("");
              setSceneOpening("");
            })}>Pornește scena</button>
          </div>
        ) : (
          <div className="theatre-form">
            <p className="muted">Scena activă: {activeScene.title}</p>
            <RichTextEditor id="theatre-stage-direction" value={direction} onChange={setDirection} maxLength={8000} mentionSearch={searchUsers} />
            <button className="cal-btn" type="button" disabled={!direction || busy === "direction"} onClick={() => run("direction", async () => {
              await createTheatreStageDirection(play.id, activeScene.id, { content: direction });
              setDirection("");
            })}>Adaugă indicație scenică</button>
            <div className="theatre-form-row">
              <select className="cal-input" value={overrideCharacterId} onChange={(event) => setOverrideCharacterId(event.target.value)}>
                <option value="">Schimbă rândul către</option>
                {assignedCharacters.map((character) => <option value={character.id} key={character.id}>{character.name} · {character.assigned_user?.username}</option>)}
              </select>
              <input className="cal-input" value={overrideNote} onChange={(event) => setOverrideNote(event.target.value)} placeholder="notă opțională" />
              <button className="cal-btn" type="button" disabled={!overrideCharacterId} onClick={() => run("override", async () => {
                await overrideTheatreTurn(play.id, { character_id: Number(overrideCharacterId), note: overrideNote || undefined });
                setOverrideCharacterId("");
                setOverrideNote("");
              })}>Schimbă rândul</button>
            </div>
            <RichTextEditor id="theatre-scene-end" value={endNote} onChange={setEndNote} maxLength={8000} mentionSearch={searchUsers} />
            <button className="cal-btn danger" type="button" onClick={() => run("end", async () => {
              await endTheatreScene(play.id, activeScene.id, { content: endNote || undefined });
              setEndNote("");
            })}>Încheie scena</button>
          </div>
        )}
        {error ? <div className="inline-error">{error}</div> : null}
      </section>
    </div>
  );
}

function ParticipantConsole({ play, user, onRefresh }) {
  const activeScene = (play.scenes || []).find((scene) => scene.id === play.current_scene_id && scene.status === "active");
  const myTurn = Boolean(user && play.current_actor_user_id === user.id && activeScene);
  const [applyCharacterId, setApplyCharacterId] = useState("");
  const [applyNote, setApplyNote] = useState("");
  const [proposeName, setProposeName] = useState("");
  const [proposeDescription, setProposeDescription] = useState("");
  const [newCharacterName, setNewCharacterName] = useState("");
  const [newCharacterDescription, setNewCharacterDescription] = useState("");
  const [reply, setReply] = useState("");
  const [nextCharacterId, setNextCharacterId] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const assignedCharacters = readyCharacters(play);
  const freeCharacters = availableCharacters(play);
  const isMember = Boolean(play.my_role);

  const run = async (key, action) => {
    if (busy) return;
    setBusy(key);
    setError("");
    try {
      await action();
      await onRefresh();
    } catch (requestError) {
      setError(requestError.message || "Acțiunea a eșuat.");
    } finally {
      setBusy("");
    }
  };

  if (!user) {
    return <StatusPanel title="Participarea cere autentificare">Poți citi piesa public, dar trebuie să intri în cont ca să aplici sau să scrii.</StatusPanel>;
  }

  return (
    <div className="theatre-console-grid">
      {!isMember ? (
        <section className="theatre-panel">
          <h2>Participă</h2>
          {play.my_pending_request ? (
            <div className="theatre-request">
              <div>
                <strong>{statusLabel(play.my_pending_request.direction)} în așteptare</strong>
                <span>{play.my_pending_request.character?.name || "fără personaj ales"}</span>
              </div>
              {play.my_pending_request.direction === "invitation" ? (
                <div className="theatre-inline-actions">
                  <button className="cal-btn primary" type="button" onClick={() => run("accept-invite", () => respondTheatreRequest(play.id, play.my_pending_request.id, { action: "approve" }))}>Acceptă</button>
                  <button className="cal-btn danger" type="button" onClick={() => run("reject-invite", () => respondTheatreRequest(play.id, play.my_pending_request.id, { action: "reject" }))}>Refuză</button>
                </div>
              ) : null}
            </div>
          ) : (
            <div className="theatre-form">
              <select className="cal-input" value={applyCharacterId} onChange={(event) => setApplyCharacterId(event.target.value)} disabled={Boolean(proposeName.trim() || proposeDescription.trim())}>
                <option value="">Alege personaj disponibil</option>
                {freeCharacters.map((character) => <option value={character.id} key={character.id}>{character.name}</option>)}
              </select>
              <input className="cal-input" value={proposeName} onChange={(event) => setProposeName(event.target.value)} placeholder="sau propune personaj nou" disabled={Boolean(applyCharacterId)} />
              <textarea className="cal-textarea" value={proposeDescription} onChange={(event) => setProposeDescription(event.target.value)} placeholder="descriere personaj nou" rows={3} disabled={Boolean(applyCharacterId)} />
              <textarea className="cal-textarea" value={applyNote} onChange={(event) => setApplyNote(event.target.value)} placeholder="mesaj opțional" rows={3} />
              <button className="cal-btn primary" type="button" disabled={busy === "apply"} onClick={() => run("apply", async () => {
                await applyToTheatrePlay(play.id, {
                  character_id: applyCharacterId ? Number(applyCharacterId) : undefined,
                  proposed_character: proposeName.trim() ? { name: proposeName, description: proposeDescription } : undefined,
                  note: applyNote || undefined
                });
                setApplyCharacterId("");
                setProposeName("");
                setProposeDescription("");
                setApplyNote("");
              })}>Trimite cerere</button>
            </div>
          )}
        </section>
      ) : (
        <section className="theatre-panel">
          <h2>Personaj nou</h2>
          <input className="cal-input" value={newCharacterName} onChange={(event) => setNewCharacterName(event.target.value)} placeholder="Nume personaj" />
          <textarea className="cal-textarea" value={newCharacterDescription} onChange={(event) => setNewCharacterDescription(event.target.value)} placeholder="Descriere" rows={3} />
          <button className="cal-btn" type="button" disabled={!newCharacterName.trim() || !newCharacterDescription.trim()} onClick={() => run("character", async () => {
            await createTheatreCharacter(play.id, { name: newCharacterName, description: newCharacterDescription });
            setNewCharacterName("");
            setNewCharacterDescription("");
          })}>Propune personaj</button>
        </section>
      )}
      {myTurn ? (
        <section className="theatre-panel wide">
          <h2>Este rândul tău</h2>
          <RichTextEditor id="theatre-reply" value={reply} onChange={setReply} maxLength={8000} mentionSearch={searchUsers} />
          <select className="cal-input" value={nextCharacterId} onChange={(event) => setNextCharacterId(event.target.value)}>
            <option value="">Alege următorul personaj</option>
            {assignedCharacters.map((character) => <option value={character.id} key={character.id}>{character.name} · {character.assigned_user?.username}</option>)}
          </select>
          <button className="cal-btn primary" type="button" disabled={!reply || !nextCharacterId || busy === "reply"} onClick={() => run("reply", async () => {
            await createTheatreReply(play.id, activeScene.id, { content: reply, next_character_id: Number(nextCharacterId) });
            setReply("");
            setNextCharacterId("");
          })}>Trimite replica</button>
        </section>
      ) : isMember ? (
        <section className="theatre-panel">
          <h2>Rând curent</h2>
          <p className="muted">{play.current_character ? `${play.current_character.name} · ${play.current_character.assigned_user?.username || ""}` : "Nu există rând activ."}</p>
        </section>
      ) : null}
      {error ? <div className="inline-error theatre-console-error">{error}</div> : null}
    </div>
  );
}

function CastList({ play }) {
  return (
    <section className="theatre-panel">
      <h2>Distribuție</h2>
      <div className="theatre-cast">
        {(play.characters || []).map((character) => (
          <article className={`theatre-cast-card ${character.status}`} key={character.id}>
            <div className="theatre-cast-head">
              <strong>{character.name}</strong>
              <span>{character.status === "approved" ? assignmentStatusLabel(assignmentStatus(character)) : statusLabel(character.status)}</span>
            </div>
            <p>{character.description}</p>
            <div className="theatre-cast-meta">
              {character.assigned_user ? <span>{usernameHandle(character.assigned_user.username)}</span> : null}
              {!character.assigned_user && character.pending_invitation_user ? <span>invitat: {usernameHandle(character.pending_invitation_user.username)}</span> : null}
              {!character.assigned_user && !character.pending_invitation_user ? <span>neatribuit</span> : null}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function SceneList({ play }) {
  return (
    <section className="theatre-scenes">
      {(play.scenes || []).length ? play.scenes.map((scene) => (
        <article className="theatre-scene" key={scene.id}>
          <header className="theatre-scene-head">
            <span>Scena {scene.scene_number}</span>
            <h2>{scene.title}</h2>
            <small>{statusLabel(scene.status)}</small>
          </header>
          <div className="theatre-entry-list">
            {scene.entries?.length ? scene.entries.map((entry) => (
              <section className={`theatre-entry ${entry.entry_type} ${entry.moderation_status}`} key={entry.id}>
                <div className="theatre-entry-meta">
                  <span>{entry.character?.name || entryTypeLabel(entry.entry_type)}</span>
                  {entry.moderation_status !== "approved" ? <em>{statusLabel(entry.moderation_status)}</em> : null}
                  <small>{formatDateTime(entry.created_at)}</small>
                </div>
                <RichTextContent html={entry.content} className={entry.entry_type === "line" ? "" : "theatre-parenthetical-content"} />
              </section>
            )) : <p className="muted">Scena nu are încă text public aprobat.</p>}
          </div>
        </article>
      )) : <StatusPanel title="Nu există scene încă" />}
    </section>
  );
}

function TheatrePlayView({ slug, user }) {
  const [play, setPlay] = useState(null);
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const data = await fetchTheatrePlay(slug);
    setPlay(data);
    if (user && data.creator_id === user.id) {
      const requestData = await fetchTheatreRequests(data.id);
      setRequests(requestData.requests || []);
    } else {
      setRequests([]);
    }
    return data;
  }, [slug, user?.id]);

  const refresh = useCallback(async () => {
    try {
      const data = await load();
      setError("");
      return data;
    } catch (requestError) {
      setError(requestError.message || "Nu am putut încărca piesa.");
      throw requestError;
    }
  }, [load]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    load()
      .then(() => {
        if (!cancelled) setError("");
      })
      .catch((requestError) => {
        if (!cancelled) setError(requestError.message || "Nu am putut încărca piesa.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [load]);

  useEffect(() => {
    if (!play || play.status !== "active") return undefined;
    const timer = window.setInterval(() => {
      refresh().catch(() => {});
    }, 30000);
    return () => window.clearInterval(timer);
  }, [play?.id, play?.status, refresh]);

  const isCreator = Boolean(user && play?.creator_id === user.id);
  const pdfHref = play?.slug ? theatrePdfUrl(play.slug) : "#";
  usePageSeo(play ? theatrePlaySeo(play) : null, [play?.id, play?.updated_at, play?.status]);

  return (
    <PageShell kicker="teatru colaborativ" title={play?.title || "Piesă"} sub={play?.description || "Piesă colaborativă."}>
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca piesa">{error}</StatusPanel> : null}
      {play ? (
        <div className="theatre-detail">
          <div className="theatre-toolbar">
            <div>
              <span className={`theatre-status ${play.status}`}>{statusLabel(play.status)}</span>
              {play.creator ? <AuthorLink user={play.creator} /> : null}
            </div>
            <a className="cal-btn" href={pdfHref} download>PDF</a>
          </div>
          <CastList play={play} />
          {isCreator ? <CreatorConsole play={play} requests={requests} onRefresh={refresh} /> : <ParticipantConsole play={play} user={user} onRefresh={refresh} />}
          <SceneList play={play} />
        </div>
      ) : null}
    </PageShell>
  );
}

export default function TheatreRoute({ route, user }) {
  if (route.name === "theatreCreate") return <TheatreCreateView user={user} />;
  if (route.name === "theatrePlay") return <TheatrePlayView slug={route.slug} user={user} />;
  return <TheatreListView user={user} />;
}
