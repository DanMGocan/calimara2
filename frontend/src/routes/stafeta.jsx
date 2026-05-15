import { useCallback, useEffect, useMemo, useState } from "react";
import { FiRepeat, FiSend, FiUserCheck } from "react-icons/fi";
import {
  assignStafetaRandom,
  assignStafetaSpecific,
  cancelStafeta,
  createStafetaWork,
  fetchStafetaWork,
  fetchStafetaWorks,
  publishStafeta,
  respondStafetaAssignment,
  sendStafetaForward,
  updateStafetaParticipation
} from "../api/stafeta.js";
import { searchUsers } from "../api/users.js";
import { CATEGORY_LABELS } from "../app/constants.js";
import { AuthorLink, RichTextContent } from "../app/content.jsx";
import { RichTextEditor } from "../app/editor.jsx";
import { formatDateTime, formatNumber, htmlToText, usernameHandle } from "../app/format.js";
import { useAsync } from "../app/hooks.js";
import { AuthRequired, PageShell, StatusPanel } from "../app/layout.jsx";
import { blogUrl, mainPath } from "../app/paths.js";

const FILTERS = [
  ["all", "Toate"],
  ["turn", "Rândul meu"],
  ["created", "Create de mine"],
  ["published", "Publicate"]
];

function statusLabel(value) {
  return {
    active: "activă",
    published: "publicată",
    cancelled: "anulată",
    pending: "în așteptare",
    approved: "aprobat",
    flagged: "în revizie",
    rejected: "respins",
    random: "aleatoriu",
    creator: "creator",
    previous: "participant anterior",
    specific: "utilizator ales"
  }[value] || value || "";
}

function assignmentStatus(assignment) {
  if (!assignment) return "Fără rând activ.";
  if (assignment.status === "pending") return `Invitație trimisă către ${usernameHandle(assignment.user?.username)}.`;
  if (assignment.status === "active") return `Rândul este la ${usernameHandle(assignment.user?.username)}.`;
  return statusLabel(assignment.status);
}

function UserSearchInput({ id, value, onChange, label, placeholder }) {
  const [state, setState] = useState({ results: [], loading: false, error: "" });

  useEffect(() => {
    const term = value.trim();
    if (term.length < 3) {
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
        .catch((error) => {
          if (!cancelled) setState({ results: [], loading: false, error: error.message || "Nu am putut căuta utilizatori." });
        });
    }, 220);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [value]);

  return (
    <div className="stafeta-user-search">
      <label className="cal-label" htmlFor={id}>{label}</label>
      <input id={id} className="cal-input" value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder || label} minLength="3" maxLength="255" />
      {state.loading ? <div className="theatre-suggestions-note">Se caută utilizatori...</div> : null}
      {state.error ? <div className="inline-error">{state.error}</div> : null}
      {!state.loading && state.results.length ? (
        <div className="theatre-user-suggestions">
          {state.results.map((result) => (
            <button className="theatre-user-suggestion" type="button" key={result.id} onClick={() => onChange(result.username)}>
              <strong>{usernameHandle(result.username)}</strong>
              {result.subtitle ? <span>{result.subtitle}</span> : null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function ParticipationToggle({ participates, onChange }) {
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");

  const toggle = async () => {
    if (busy) return;
    const next = !participates;
    setBusy(true);
    setStatus("");
    try {
      const result = await updateStafetaParticipation(next);
      onChange(Boolean(result?.participates));
      setStatus(result?.participates ? "Participi la tragerile aleatorii." : "Nu mai primești Ștafete aleatorii.");
    } catch (error) {
      setStatus(error.message || "Nu am putut salva participarea.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stafeta-participation">
      <label className="email-preference-toggle">
        <input type="checkbox" checked={participates} onChange={toggle} disabled={busy} />
        <span>Particip la Ștafeta</span>
      </label>
      {status ? <div className={status.includes("Nu am putut") ? "inline-error" : "inline-status"}>{status}</div> : null}
    </div>
  );
}

function StafetaListView({ user }) {
  const [filter, setFilter] = useState("all");
  const [refreshKey, setRefreshKey] = useState(0);
  const { data, loading, error } = useAsync(() => fetchStafetaWorks({ filter }), [filter, refreshKey]);
  const [participates, setParticipates] = useState(Boolean(user?.stafeta_participates));

  useEffect(() => {
    setParticipates(Boolean(data?.participates ?? user?.stafeta_participates));
  }, [data?.participates, user?.stafeta_participates]);

  if (!user) return <AuthRequired />;

  return (
    <PageShell
      kicker="Ștafeta"
      title="Ștafeta"
      sub="Texte private continuate pe rând, publicate de creator când sunt gata."
      titleAction={<a className="cal-btn primary" href={mainPath("/stafeta/nou")}>Creează Ștafeta</a>}
    >
      <section className="stafeta-toolbar">
        <ParticipationToggle
          participates={participates}
          onChange={(value) => {
            setParticipates(value);
            setRefreshKey((key) => key + 1);
          }}
        />
        <div className="stafeta-filters" role="tablist" aria-label="Filtre Ștafeta">
          {FILTERS.map(([key, label]) => (
            <button className={`cal-btn ${filter === key ? "primary" : ""}`.trim()} type="button" key={key} onClick={() => setFilter(key)}>
              {label}
            </button>
          ))}
        </div>
      </section>
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca Ștafeta">{error.message || String(error)}</StatusPanel> : null}
      {data?.works?.length ? (
        <div className="list-grid stafeta-list">
          {data.works.map((work) => (
            <article className="piece-card stafeta-card" key={work.id}>
              <div className="piece-card-kicker">{statusLabel(work.status)} · {CATEGORY_LABELS[work.category] || work.category}</div>
              <h2 className="piece-card-title"><a className="post-title-link" href={mainPath(`/stafeta/${work.slug}`)}>{work.title}</a></h2>
              <p className="piece-card-excerpt">{assignmentStatus(work.current_assignment)}</p>
              <div className="piece-card-meta">
                <span>{formatNumber(work.approved_segment_count)} fragmente</span>
                <span>{formatNumber(work.participant_count)} participanți</span>
                {work.creator ? <AuthorLink user={work.creator} /> : null}
              </div>
            </article>
          ))}
        </div>
      ) : !loading && !error ? <StatusPanel title="Nu există Ștafete aici" /> : null}
    </PageShell>
  );
}

function StafetaCreateView({ user }) {
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("poezie");
  const [initialContent, setInitialContent] = useState("");
  const [deadlineDays, setDeadlineDays] = useState(1);
  const [maxCharacters, setMaxCharacters] = useState(400);
  const [firstTargetMode, setFirstTargetMode] = useState("random");
  const [assignedUsername, setAssignedUsername] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  if (!user) return <AuthRequired />;

  const submit = async (event) => {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError("");
    try {
      const work = await createStafetaWork({
        title: title.trim(),
        category,
        initial_content: initialContent,
        deadline_days: Number(deadlineDays),
        max_characters: Number(maxCharacters) || 400,
        first_target_mode: firstTargetMode,
        assigned_username: firstTargetMode === "specific" ? assignedUsername.trim() : undefined
      });
      window.location.href = mainPath(`/stafeta/${work.slug}`);
    } catch (requestError) {
      setError(requestError.message || "Nu am putut crea Ștafeta.");
      setSubmitting(false);
    }
  };

  return (
    <PageShell kicker="Ștafeta" title="Ștafetă nouă" sub="Scrie începutul și trimite textul mai departe.">
      <form className="theatre-form stafeta-create-form" onSubmit={submit}>
        <label className="cal-label" htmlFor="stafeta-title">Titlu</label>
        <input id="stafeta-title" className="cal-input" value={title} onChange={(event) => setTitle(event.target.value)} maxLength={160} required />
        <label className="cal-label" htmlFor="stafeta-category">Tip text</label>
        <select id="stafeta-category" className="cal-input" value={category} onChange={(event) => setCategory(event.target.value)}>
          <option value="poezie">Poezie</option>
          <option value="proza_scurta">Proză scurtă</option>
        </select>
        <label className="cal-label" htmlFor="stafeta-initial">Început</label>
        <RichTextEditor id="stafeta-initial" value={initialContent} onChange={setInitialContent} maxLength={10000} mentionSearch={searchUsers} />
        <div className="theatre-form-row">
          <label className="cal-label" htmlFor="stafeta-deadline">Timp la fiecare participant</label>
          <select id="stafeta-deadline" className="cal-input" value={deadlineDays} onChange={(event) => setDeadlineDays(Number(event.target.value))}>
            <option value={1}>1 zi</option>
            <option value={3}>3 zile</option>
            <option value={7}>7 zile</option>
          </select>
          <label className="cal-label" htmlFor="stafeta-max">Numărul maxim de caractere:</label>
          <input id="stafeta-max" className="cal-input" type="number" min="1" max="10000" value={maxCharacters} onChange={(event) => setMaxCharacters(event.target.value)} />
        </div>
        <fieldset className="stafeta-target-fieldset">
          <legend className="cal-label">Prima trimitere</legend>
          <label className="email-preference-toggle">
            <input type="radio" name="first-target" checked={firstTargetMode === "random"} onChange={() => setFirstTargetMode("random")} />
            <span>Aleatoriu din participanții înscriși</span>
          </label>
          <label className="email-preference-toggle">
            <input type="radio" name="first-target" checked={firstTargetMode === "specific"} onChange={() => setFirstTargetMode("specific")} />
            <span>Utilizator ales</span>
          </label>
        </fieldset>
        {firstTargetMode === "specific" ? (
          <UserSearchInput id="stafeta-first-user" value={assignedUsername} onChange={setAssignedUsername} label="Utilizator" placeholder="Caută după username" />
        ) : null}
        <div className="theatre-form-actions">
          <button className="cal-btn primary" type="submit" disabled={submitting || !title.trim() || !htmlToText(initialContent)}>
            {submitting ? "Se creează..." : "Creează și trimite"}
          </button>
          {error ? <span className="inline-error">{error}</span> : null}
        </div>
      </form>
    </PageShell>
  );
}

function CreatorControls({ work, onRefresh }) {
  const [username, setUsername] = useState("");
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");

  const run = async (key, action) => {
    if (busy) return;
    setBusy(key);
    setStatus("");
    try {
      await action();
      await onRefresh();
    } catch (error) {
      setStatus(error.message || "Acțiunea a eșuat.");
    } finally {
      setBusy("");
    }
  };

  if (work.status !== "active") return null;

  return (
    <section className="theatre-panel stafeta-control-panel">
      <h2>Control creator</h2>
      <div className="theatre-form-row">
        <button className="cal-btn" type="button" disabled={Boolean(busy)} onClick={() => run("random", () => assignStafetaRandom(work.id))}>
          Trimite aleatoriu
        </button>
        <button className="cal-btn primary" type="button" disabled={Boolean(busy)} onClick={() => run("publish", () => publishStafeta(work.id))}>
          Închide și publică
        </button>
        <button className="cal-btn danger" type="button" disabled={Boolean(busy)} onClick={() => run("cancel", () => cancelStafeta(work.id))}>
          Anulează
        </button>
      </div>
      <UserSearchInput id="stafeta-assign-user" value={username} onChange={setUsername} label="Trimite către utilizator ales" />
      <button className="cal-btn" type="button" disabled={!username.trim() || Boolean(busy)} onClick={() => run("specific", async () => {
        await assignStafetaSpecific(work.id, { username });
        setUsername("");
      })}>Trimite invitație</button>
      {status ? <div className={status.includes("eșuat") || status.includes("Nu am") ? "inline-error" : "inline-status"}>{status}</div> : null}
    </section>
  );
}

function InvitationPanel({ work, assignment, onRefresh }) {
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");

  const respond = async (action) => {
    if (busy) return;
    setBusy(action);
    setStatus("");
    try {
      await respondStafetaAssignment(work.id, assignment.id, { action });
      await onRefresh();
    } catch (error) {
      setStatus(error.message || "Nu am putut răspunde invitației.");
    } finally {
      setBusy("");
    }
  };

  return (
    <section className="theatre-panel stafeta-control-panel">
      <h2>Ai primit Ștafeta</h2>
      <p className="muted">Poți accepta rândul sau o poți trimite înapoi creatorului.</p>
      <div className="theatre-inline-actions">
        <button className="cal-btn primary" type="button" disabled={Boolean(busy)} onClick={() => respond("accept")}>Acceptă</button>
        <button className="cal-btn danger" type="button" disabled={Boolean(busy)} onClick={() => respond("refuse")}>Refuză</button>
      </div>
      {status ? <div className="inline-error">{status}</div> : null}
    </section>
  );
}

function ContributorPanel({ work, onRefresh }) {
  const [content, setContent] = useState("");
  const [targetMode, setTargetMode] = useState("random");
  const [targetUserId, setTargetUserId] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const plainLength = htmlToText(content).length;
  const hasContent = plainLength > 0;
  const previous = work.previous_participants || [];

  const submit = async () => {
    if (busy) return;
    setBusy(true);
    setStatus("");
    try {
      await sendStafetaForward(work.id, {
        content: hasContent ? content : undefined,
        target_mode: hasContent ? targetMode : "random",
        target_user_id: hasContent && targetMode === "previous" ? Number(targetUserId) : undefined
      });
      setContent("");
      setTargetMode("random");
      setTargetUserId("");
      await onRefresh();
      setStatus(hasContent ? "Contribuția a fost trimisă la moderare." : "Ștafeta a mers mai departe.");
    } catch (error) {
      setStatus(error.message || "Nu am putut trimite Ștafeta.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="theatre-panel wide stafeta-write-panel">
      <h2>Este rândul tău</h2>
      <RichTextEditor id="stafeta-contribution" value={content} onChange={setContent} maxLength={work.max_characters} mentionSearch={searchUsers} />
      <div className={`stafeta-char-count ${plainLength > work.max_characters ? "over" : ""}`.trim()}>
        {formatNumber(plainLength)} / {formatNumber(work.max_characters)} caractere
      </div>
      {hasContent ? (
        <div className="stafeta-destination-grid">
          <label className="email-preference-toggle">
            <input type="radio" name="stafeta-target" checked={targetMode === "random"} onChange={() => setTargetMode("random")} />
            <span>Aleatoriu</span>
          </label>
          <label className="email-preference-toggle">
            <input type="radio" name="stafeta-target" checked={targetMode === "creator"} onChange={() => setTargetMode("creator")} />
            <span>Înapoi la creator</span>
          </label>
          <label className="email-preference-toggle">
            <input type="radio" name="stafeta-target" checked={targetMode === "previous"} onChange={() => setTargetMode("previous")} disabled={!previous.length} />
            <span>Participant anterior</span>
          </label>
          {targetMode === "previous" ? (
            <select className="cal-input" value={targetUserId} onChange={(event) => setTargetUserId(event.target.value)}>
              <option value="">Alege participantul</option>
              {previous.map((item) => (
                <option value={item.user.id} key={item.user.id}>{item.user.username}</option>
              ))}
            </select>
          ) : null}
        </div>
      ) : <p className="muted">Dacă trimiți fără text, Ștafeta intră automat în grupul aleatoriu.</p>}
      <button className="cal-btn primary" type="button" disabled={busy || plainLength > work.max_characters || (hasContent && targetMode === "previous" && !targetUserId)} onClick={submit}>
        <FiSend aria-hidden="true" /> Trimite Ștafeta
      </button>
      {status ? <div className={status.includes("Nu am") || status.includes("depășește") ? "inline-error" : "inline-status"}>{status}</div> : null}
    </section>
  );
}

function StafetaTimeline({ work }) {
  return (
    <section className="stafeta-timeline">
      {work.segments?.length ? work.segments.map((segment) => (
        <article className={`theatre-entry stafeta-segment ${segment.moderation_status}`} key={segment.id}>
          <div className="theatre-entry-meta">
            <span>{segment.author ? usernameHandle(segment.author.username) : "Autor"}</span>
            {segment.moderation_status !== "approved" ? <em>{statusLabel(segment.moderation_status)}</em> : null}
            <small>{formatDateTime(segment.created_at)}</small>
          </div>
          <RichTextContent html={segment.content} />
        </article>
      )) : <StatusPanel title="Nu există fragmente încă" />}
    </section>
  );
}

function StafetaDetailView({ slug, user }) {
  const [work, setWork] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const data = await fetchStafetaWork(slug);
    setWork(data);
    return data;
  }, [slug]);

  const refresh = useCallback(async () => {
    try {
      const data = await load();
      setError("");
      return data;
    } catch (requestError) {
      setError(requestError.message || "Nu am putut încărca Ștafeta.");
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
        if (!cancelled) setError(requestError.message || "Nu am putut încărca Ștafeta.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [load]);

  const isCreator = Boolean(user && work?.creator_id === user.id);
  const currentAssignment = work?.current_assignment;
  const publishedHref = work?.published_post_slug && work?.creator?.username
    ? `${blogUrl(work.creator.username)}/${work.published_post_slug}`
    : "";

  return (
    <PageShell kicker="Ștafeta" title={work?.title || "Ștafeta"} sub={work ? `${CATEGORY_LABELS[work.category] || work.category} · ${statusLabel(work.status)}` : ""}>
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca Ștafeta">{error}</StatusPanel> : null}
      {work ? (
        <div className="theatre-detail stafeta-detail">
          <div className="theatre-toolbar">
            <div>
              <span className={`theatre-status ${work.status}`}>{statusLabel(work.status)}</span>
              {work.creator ? <AuthorLink user={work.creator} /> : null}
            </div>
            {publishedHref ? <a className="cal-btn" href={publishedHref}>Postarea publicată</a> : null}
          </div>
          <section className="theatre-panel stafeta-current">
            <h2>Rând curent</h2>
            <p className="muted">{assignmentStatus(currentAssignment)}</p>
            {currentAssignment?.due_at ? <p className="muted">Termen: {formatDateTime(currentAssignment.due_at)}</p> : null}
          </section>
          {work.can_respond ? <InvitationPanel work={work} assignment={currentAssignment} onRefresh={refresh} /> : null}
          {work.can_write ? <ContributorPanel work={work} onRefresh={refresh} /> : null}
          {isCreator ? <CreatorControls work={work} onRefresh={refresh} /> : null}
          <StafetaTimeline work={work} />
        </div>
      ) : null}
    </PageShell>
  );
}

export default function StafetaRoute({ route, user }) {
  if (route.name === "stafetaCreate") return <StafetaCreateView user={user} />;
  if (route.name === "stafetaWork") return <StafetaDetailView slug={route.slug} user={user} />;
  return <StafetaListView user={user} />;
}
