import { useCallback, useEffect, useState } from "react";
import {
  bulkAdminForumThreads,
  createAdminForumSection,
  deleteAdminForumSection,
  fetchAdminForumSections,
  fetchAdminForumThreads,
  reorderAdminForumSections,
  updateAdminForumSection
} from "../api/forum.js";
import { AuthorLink } from "../app/content.jsx";
import { formatDateTime, formatNumber } from "../app/format.js";
import { mainPath } from "../app/paths.js";

const EMPTY_SECTION_FORM = { name: "", slug: "", description: "", staff_only: false, is_featured: false, is_archived: false };
const THREAD_STATUS_LABELS = { approved: "aprobată", pending: "în așteptare", flagged: "marcată", rejected: "respinsă" };
const THREADS_PER_PAGE = 50;

function ForumAdminPanel({ title, description, actions, children }) {
  return (
    <section className="admin-panel">
      <div className="admin-panel-head">
        <div className="admin-panel-title-group">
          <h2>{title}</h2>
          {description ? <p>{description}</p> : null}
        </div>
        {actions ? <div className="admin-panel-actions">{actions}</div> : null}
      </div>
      {children}
    </section>
  );
}

function sectionToForm(section) {
  return {
    name: section.label || "",
    slug: section.key || "",
    description: section.description || "",
    staff_only: Boolean(section.staff_only),
    is_featured: Boolean(section.featured),
    is_archived: Boolean(section.is_archived)
  };
}

function SectionForm({ initial, editing, busy, onSubmit, onCancel }) {
  const [form, setForm] = useState(initial);
  const update = (field) => (event) => {
    const value = event.target.type === "checkbox" ? event.target.checked : event.target.value;
    setForm((current) => ({ ...current, [field]: value }));
  };
  const submit = (event) => {
    event.preventDefault();
    onSubmit({
      name: form.name,
      slug: form.slug.trim() || (editing ? undefined : null),
      description: form.description,
      staff_only: form.staff_only,
      is_featured: form.is_featured,
      is_archived: form.is_archived
    });
  };
  return (
    <form className="form-stack admin-forum-form" onSubmit={submit}>
      <label className="auth-field" htmlFor="forum-section-name">Nume</label>
      <input id="forum-section-name" className="cal-input" value={form.name} onChange={update("name")} maxLength={80} required />
      <label className="auth-field" htmlFor="forum-section-slug">Identificator în adresă {editing ? "" : "(opțional, se generează din nume)"}</label>
      <input
        id="forum-section-slug"
        className="cal-input"
        value={form.slug}
        onChange={update("slug")}
        maxLength={60}
        pattern="[a-z0-9][a-z0-9_\-]*"
        placeholder="ex: atelier-de-proza"
        title="Litere mici, cifre, - și _"
      />
      {editing && initial.slug && form.slug.trim() && form.slug.trim() !== initial.slug ? (
        <p className="auth-sub">Discuțiile existente vor fi mutate automat la noul identificator. Legăturile vechi către secțiune nu vor mai funcționa.</p>
      ) : null}
      <label className="auth-field" htmlFor="forum-section-description">Descriere</label>
      <textarea id="forum-section-description" className="cal-input" value={form.description} onChange={update("description")} maxLength={300} rows={2} />
      <label className="admin-forum-check">
        <input type="checkbox" checked={form.staff_only} onChange={update("staff_only")} />
        <span>Doar adminii și moderatorii pot deschide discuții (toți pot răspunde)</span>
      </label>
      <label className="admin-forum-check">
        <input type="checkbox" checked={form.is_featured} onChange={update("is_featured")} />
        <span>Evidențiată în lista de secțiuni</span>
      </label>
      <label className="admin-forum-check">
        <input type="checkbox" checked={form.is_archived} onChange={update("is_archived")} />
        <span>Arhivată (se poate citi, dar nu primește discuții sau răspunsuri noi)</span>
      </label>
      <div className="button-row">
        <button className="cal-btn primary" type="submit" disabled={busy}>{editing ? "Salvează secțiunea" : "Creează secțiunea"}</button>
        <button className="cal-btn" type="button" onClick={onCancel} disabled={busy}>Renunță</button>
      </div>
    </form>
  );
}

function SectionDeleteControls({ section, sections, busy, onDelete, onCancel }) {
  const targets = sections.filter((item) => item.id !== section.id);
  const [target, setTarget] = useState(targets[0]?.key || "");
  return (
    <div className="admin-forum-delete">
      <span>Secțiunea are {formatNumber(section.total_thread_count)} discuții. Mută-le în:</span>
      <select className="cal-input" value={target} onChange={(event) => setTarget(event.target.value)} aria-label="Secțiunea de destinație">
        {targets.map((item) => <option key={item.id} value={item.key}>{item.label}</option>)}
      </select>
      <button className="cal-btn danger" type="button" disabled={busy || !target} onClick={() => onDelete(section, target)}>Mută și șterge</button>
      <button className="cal-btn" type="button" disabled={busy} onClick={onCancel}>Renunță</button>
    </div>
  );
}

function AdminForumSections({ busy, setBusy, setStatus, sections, setSections }) {
  const [editing, setEditing] = useState(null); // null | "new" | section id
  const [deleting, setDeleting] = useState(null);

  const run = async (label, action, success) => {
    setBusy(label);
    setStatus("");
    try {
      const result = await action();
      if (success) setStatus(success);
      return result;
    } catch (requestError) {
      setStatus(requestError.message || "Acțiunea nu a reușit.");
      return null;
    } finally {
      setBusy("");
    }
  };

  const refresh = async () => {
    const response = await fetchAdminForumSections();
    setSections(response.sections || []);
  };

  const saveSection = async (data) => {
    const isNew = editing === "new";
    const payload = Object.fromEntries(Object.entries(data).filter(([, value]) => value !== undefined));
    const saved = await run(
      "section-save",
      () => (isNew ? createAdminForumSection(payload) : updateAdminForumSection(editing, payload)),
      isNew ? "Secțiunea a fost creată." : "Secțiunea a fost salvată."
    );
    if (saved) {
      setEditing(null);
      await refresh();
    }
  };

  const move = async (index, offset) => {
    const next = [...sections];
    const [item] = next.splice(index, 1);
    next.splice(index + offset, 0, item);
    const response = await run("section-order", () => reorderAdminForumSections(next.map((section) => section.id)));
    if (response) setSections(response.sections || []);
  };

  const toggleArchive = async (section) => {
    const saved = await run(
      `section-archive-${section.id}`,
      () => updateAdminForumSection(section.id, { is_archived: !section.is_archived }),
      section.is_archived ? "Secțiunea a fost redeschisă." : "Secțiunea a fost arhivată."
    );
    if (saved) await refresh();
  };

  const deleteSection = async (section, moveTo) => {
    if (!moveTo && !window.confirm(`Ștergi secțiunea „${section.label}”?`)) return;
    const response = await run(
      `section-delete-${section.id}`,
      () => deleteAdminForumSection(section.id, moveTo),
      moveTo ? "Discuțiile au fost mutate, iar secțiunea a fost ștearsă." : "Secțiunea a fost ștearsă."
    );
    if (response) {
      setDeleting(null);
      setSections(response.sections || []);
    }
  };

  const requestDelete = (section) => {
    if (section.total_thread_count > 0) {
      setDeleting(section.id);
      return;
    }
    deleteSection(section, undefined);
  };

  return (
    <ForumAdminPanel
      title="Secțiuni forum"
      description="Ordinea de aici este ordinea din /discutii. Secțiunile arhivate rămân lizibile."
      actions={editing === "new" ? null : <button className="cal-btn primary" type="button" disabled={Boolean(busy)} onClick={() => setEditing("new")}>Secțiune nouă</button>}
    >
      {editing === "new" ? (
        <SectionForm initial={EMPTY_SECTION_FORM} editing={false} busy={Boolean(busy)} onSubmit={saveSection} onCancel={() => setEditing(null)} />
      ) : null}
      <div className="admin-feed compact">
        {sections.map((section, index) => (
          <article className={`admin-row compact ${section.is_archived ? "admin-forum-archived" : ""}`.trim()} key={section.id}>
            <div className="admin-row-head">
              <div>
                <div className="admin-badges">
                  <span className="piece-card-status">#{index + 1} · {section.key}</span>
                  {section.staff_only ? <span className="piece-card-status">doar echipa</span> : null}
                  {section.featured ? <span className="piece-card-status">evidențiată</span> : null}
                  {section.is_archived ? <span className="piece-card-status">arhivată</span> : null}
                </div>
                <h2 className="admin-row-title">
                  <a className="admin-title-link" href={mainPath(`/discutii/sectiune/${encodeURIComponent(section.key)}`)} target="_blank" rel="noreferrer">{section.label}</a>
                </h2>
              </div>
              <div className="admin-row-meta">
                <span>{formatNumber(section.thread_count)} discuții publice</span>
                <span>{formatNumber(section.total_thread_count)} în total</span>
                <span>{formatNumber(section.reply_count)} răspunsuri</span>
              </div>
            </div>
            {section.description ? <div className="admin-row-body"><p className="auth-sub">{section.description}</p></div> : null}
            {editing === section.id ? (
              <SectionForm initial={sectionToForm(section)} editing busy={Boolean(busy)} onSubmit={saveSection} onCancel={() => setEditing(null)} />
            ) : deleting === section.id ? (
              <SectionDeleteControls section={section} sections={sections} busy={Boolean(busy)} onDelete={deleteSection} onCancel={() => setDeleting(null)} />
            ) : (
              <div className="admin-actions">
                <button className="cal-btn" type="button" disabled={Boolean(busy) || index === 0} onClick={() => move(index, -1)} aria-label={`Mută ${section.label} mai sus`}>↑</button>
                <button className="cal-btn" type="button" disabled={Boolean(busy) || index === sections.length - 1} onClick={() => move(index, 1)} aria-label={`Mută ${section.label} mai jos`}>↓</button>
                <button className="cal-btn" type="button" disabled={Boolean(busy)} onClick={() => setEditing(section.id)}>Editează</button>
                <button className="cal-btn" type="button" disabled={Boolean(busy)} onClick={() => toggleArchive(section)}>{section.is_archived ? "Dezarhivează" : "Arhivează"}</button>
                <button className="cal-btn danger" type="button" disabled={Boolean(busy) || sections.length <= 1} onClick={() => requestDelete(section)}>Șterge</button>
              </div>
            )}
          </article>
        ))}
      </div>
    </ForumAdminPanel>
  );
}

function AdminForumThreads({ busy, setBusy, setStatus, sections, onChanged }) {
  const [filters, setFilters] = useState({ section: "", status: "", pinned: "", locked: "", q: "" });
  const [page, setPage] = useState(1);
  const [result, setResult] = useState({ threads: [], total: 0, pages: 1 });
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(() => new Set());
  const [moveTarget, setMoveTarget] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetchAdminForumThreads({ ...filters, q: filters.q.trim(), page, perPage: THREADS_PER_PAGE });
      setResult(response);
      setSelected(new Set());
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut încărca discuțiile.");
    } finally {
      setLoading(false);
    }
  }, [filters, page, setStatus]);

  useEffect(() => {
    const timer = window.setTimeout(load, 250);
    return () => window.clearTimeout(timer);
  }, [load]);

  const updateFilter = (field) => (event) => {
    setFilters((current) => ({ ...current, [field]: event.target.value }));
    setPage(1);
  };

  const toggle = (id) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const allSelected = result.threads.length > 0 && result.threads.every((thread) => selected.has(thread.id));
  const toggleAll = () => setSelected(allSelected ? new Set() : new Set(result.threads.map((thread) => thread.id)));

  const apply = async (action, ids = [...selected], section) => {
    if (!ids.length) return;
    if (action === "delete" && !window.confirm(`Ștergi definitiv ${ids.length} ${ids.length === 1 ? "discuție" : "discuții"} cu toate răspunsurile?`)) return;
    setBusy(`threads-${action}`);
    setStatus("");
    try {
      const response = await bulkAdminForumThreads(ids, action, section);
      setStatus(`Acțiune aplicată pe ${formatNumber(response.affected)} ${response.affected === 1 ? "discuție" : "discuții"}.`);
      await load();
      onChanged?.();
    } catch (requestError) {
      setStatus(requestError.message || "Acțiunea nu a reușit.");
    } finally {
      setBusy("");
    }
  };

  const selectedCount = selected.size;

  return (
    <ForumAdminPanel
      title="Discuții forum"
      description={`${formatNumber(result.total)} discuții${loading ? " · se încarcă…" : ""}`}
      actions={(
        <div className="admin-controls">
          <select className="cal-input" value={filters.section} onChange={updateFilter("section")} aria-label="Secțiune">
            <option value="">Toate secțiunile</option>
            {sections.map((section) => <option key={section.id} value={section.key}>{section.label}</option>)}
          </select>
          <select className="cal-input" value={filters.status} onChange={updateFilter("status")} aria-label="Status">
            <option value="">Orice status</option>
            {Object.entries(THREAD_STATUS_LABELS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select>
          <select className="cal-input" value={filters.pinned} onChange={updateFilter("pinned")} aria-label="Fixare">
            <option value="">Fixate și nefixate</option>
            <option value="true">Doar fixate</option>
            <option value="false">Doar nefixate</option>
          </select>
          <select className="cal-input" value={filters.locked} onChange={updateFilter("locked")} aria-label="Închidere">
            <option value="">Deschise și închise</option>
            <option value="true">Doar închise</option>
            <option value="false">Doar deschise</option>
          </select>
          <input className="cal-input admin-search" value={filters.q} onChange={updateFilter("q")} placeholder="Caută discuții" />
        </div>
      )}
    >
      <div className="admin-forum-bulk" role="group" aria-label="Acțiuni pe discuțiile selectate">
        <label className="admin-forum-check">
          <input type="checkbox" checked={allSelected} onChange={toggleAll} disabled={!result.threads.length} />
          <span>{selectedCount ? `${formatNumber(selectedCount)} selectate` : "Selectează tot"}</span>
        </label>
        <button className="cal-btn" type="button" disabled={Boolean(busy) || !selectedCount} onClick={() => apply("pin")}>Fixează</button>
        <button className="cal-btn" type="button" disabled={Boolean(busy) || !selectedCount} onClick={() => apply("unpin")}>Desprinde</button>
        <button className="cal-btn" type="button" disabled={Boolean(busy) || !selectedCount} onClick={() => apply("lock")}>Închide</button>
        <button className="cal-btn" type="button" disabled={Boolean(busy) || !selectedCount} onClick={() => apply("unlock")}>Redeschide</button>
        <select className="cal-input" value={moveTarget} onChange={(event) => setMoveTarget(event.target.value)} aria-label="Mută în secțiunea">
          <option value="">Mută în…</option>
          {sections.map((section) => <option key={section.id} value={section.key}>{section.label}</option>)}
        </select>
        <button className="cal-btn" type="button" disabled={Boolean(busy) || !selectedCount || !moveTarget} onClick={() => apply("move", undefined, moveTarget)}>Mută</button>
        <button className="cal-btn danger" type="button" disabled={Boolean(busy) || !selectedCount} onClick={() => apply("delete")}>Șterge</button>
      </div>
      <div className="admin-feed compact">
        {result.threads.map((thread) => (
          <article className="admin-row compact admin-forum-thread" key={thread.id}>
            <div className="admin-row-head">
              <label className="admin-forum-select">
                <input type="checkbox" checked={selected.has(thread.id)} onChange={() => toggle(thread.id)} aria-label={`Selectează ${thread.title}`} />
              </label>
              <div>
                <div className="admin-badges">
                  <span className="piece-card-status">{thread.section_label}</span>
                  <span className="piece-card-status">{THREAD_STATUS_LABELS[thread.moderation_status] || thread.moderation_status}</span>
                  {thread.is_pinned ? <span className="piece-card-status">fixată</span> : null}
                  {thread.is_locked ? <span className="piece-card-status">închisă</span> : null}
                </div>
                <h2 className="admin-row-title">
                  <a className="admin-title-link" href={mainPath(`/discutii/${thread.slug}`)} target="_blank" rel="noreferrer">{thread.title}</a>
                </h2>
              </div>
              <div className="admin-row-meta">
                {thread.author?.username ? <span><AuthorLink user={thread.author} /></span> : null}
                <span>{formatNumber(thread.reply_count)} răspunsuri · {formatNumber(thread.view_count)} vizualizări</span>
                <span>activ {formatDateTime(thread.last_activity_at)}</span>
              </div>
            </div>
            <div className="admin-actions">
              <button className="cal-btn" type="button" disabled={Boolean(busy)} onClick={() => apply(thread.is_pinned ? "unpin" : "pin", [thread.id])}>{thread.is_pinned ? "Desprinde" : "Fixează"}</button>
              <button className="cal-btn" type="button" disabled={Boolean(busy)} onClick={() => apply(thread.is_locked ? "unlock" : "lock", [thread.id])}>{thread.is_locked ? "Redeschide" : "Închide"}</button>
            </div>
          </article>
        ))}
        {!loading && !result.threads.length ? <p className="auth-sub">Nicio discuție pentru filtrele alese.</p> : null}
      </div>
      {result.pages > 1 ? (
        <div className="button-row">
          <button className="cal-btn" type="button" disabled={loading || page <= 1} onClick={() => setPage((current) => current - 1)}>‹ Înapoi</button>
          <span className="auth-sub">Pagina {page} din {result.pages}</span>
          <button className="cal-btn" type="button" disabled={loading || page >= result.pages} onClick={() => setPage((current) => current + 1)}>Înainte ›</button>
        </div>
      ) : null}
    </ForumAdminPanel>
  );
}

export function AdminForumPanel() {
  const [sections, setSections] = useState([]);
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const loadSections = useCallback(async () => {
    try {
      const response = await fetchAdminForumSections();
      setSections(response.sections || []);
      setError("");
    } catch (requestError) {
      setError(requestError.message || "Nu am putut încărca secțiunile forumului.");
    }
  }, []);

  useEffect(() => {
    loadSections();
  }, [loadSections]);

  return (
    <div className="admin-forum">
      {error ? <div className="inline-error">{error}</div> : null}
      {status ? <div className="inline-status" role="status">{status}</div> : null}
      <AdminForumSections busy={busy} setBusy={setBusy} setStatus={setStatus} sections={sections} setSections={setSections} />
      <AdminForumThreads busy={busy} setBusy={setBusy} setStatus={setStatus} sections={sections} onChanged={loadSections} />
    </div>
  );
}
