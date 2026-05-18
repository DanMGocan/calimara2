import { useEffect, useRef, useState } from "react";
import { FiAlertTriangle, FiBookOpen, FiExternalLink, FiHeart, FiImage, FiMail, FiMapPin, FiSearch, FiStar, FiTrash2, FiUpload, FiUsers } from "react-icons/fi";
import { SiYoutube } from "react-icons/si";
import { updateStafetaParticipation } from "../api/stafeta.js";
import { deleteProfileMedia, fetchPromotions, promoteAuthor, promotePost, searchPromotions, unpromoteAuthor, unpromotePost, updateEmailPreferences, updateProfileSettings, uploadProfileMedia } from "../api/users.js";
import { AUTH_COVER_OPTIONS, PROFILE_DESCRIPTION_CHARACTER_LIMIT } from "../app/constants.js";
import { RichTextEditor } from "../app/editor.jsx";
import { formatNumber, htmlToText, usernameHandle } from "../app/format.js";
import { AuthRequired, PageShell } from "../app/layout.jsx";
import { blogUrl, coverPreviewUrl, mainPath, profileAvatarUrl, profileCoverUrl } from "../app/paths.js";
import { SOCIAL_PROFILE_LINKS, SUPPORT_PROFILE_LINKS } from "../app/profile-links.jsx";

function profileFormFromUser(user) {
  return {
    subtitle: user?.subtitle || "",
    avatar_seed: user?.avatar_seed || `${user?.username || "calimara"}-shapes`,
    cover_seed: user?.cover_seed || `${user?.username || "calimara"}-cover-sky`,
    location: user?.location || "",
    youtube_playlist_url: user?.youtube_playlist_url || "",
    facebook_url: user?.facebook_url || "",
    instagram_url: user?.instagram_url || "",
    tiktok_url: user?.tiktok_url || "",
    x_url: user?.x_url || "",
    bluesky_url: user?.bluesky_url || "",
    paypal_url: user?.paypal_url || "",
    patreon_url: user?.patreon_url || "",
    buymeacoffee_url: user?.buymeacoffee_url || ""
  };
}
const PROFILE_MEDIA_RECOMMENDATIONS = {
  profil: "512 x 512 px",
  coperta: "1600 x 600 px"
};
const EMAIL_PREFERENCE_OPTIONS = [
  ["email_comment_notifications", "Comentarii noi"],
  ["email_mention_notifications", "Mențiuni"],
  ["email_analytics_digest", "Analitice avansate"],
  ["email_admin_announcements", "Anunțuri administrative"]
];
const SUPPORT_LINK_PREMIUM_TIERS = new Set(["trubadur", "cronicar", "rapsod"]);

function stafetaSlotOptions(maxSlots) {
  const limit = Math.max(1, Number(maxSlots) || 3);
  return Array.from({ length: limit }, (_item, index) => index + 1);
}

function emailPrefsFromUser(user) {
  return {
    email_comment_notifications: user?.email_comment_notifications ?? true,
    email_mention_notifications: user?.email_mention_notifications ?? true,
    email_analytics_digest: user?.email_analytics_digest ?? true,
    email_admin_announcements: user?.email_admin_announcements ?? true
  };
}

function CoverChoiceField({ username, selectedSeed, onChange }) {
  const usernameSeed = username || "calimara";
  return (
    <fieldset className="cover-choice-field profile-cover-choice-field">
      <legend className="auth-field">Copertă generată</legend>
      <div className="cover-choice-grid">
        {AUTH_COVER_OPTIONS.map((option) => {
          const seed = `${usernameSeed}-cover-${option.key}`;
          const selected = selectedSeed === seed;
          return (
            <button
              key={option.key}
              className={`cover-choice${selected ? " selected" : ""}`}
              type="button"
              aria-pressed={selected}
              onClick={() => onChange(seed)}
            >
              <img src={coverPreviewUrl(seed, 640)} alt="" aria-hidden="true" />
              <span>{option.label}</span>
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}

function ProfileMediaPanel({ user, kind, title, description, previewUrl, hasMedia, onUserUpdate }) {
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");
  const inputRef = useRef(null);
  const locked = !user?.is_premium;
  const isProfilePhoto = kind === "profil";
  const recommendation = PROFILE_MEDIA_RECOMMENDATIONS[kind];

  const upload = async (event) => {
    const file = event.target.files?.[0];
    if (!file || busy || locked) return;
    setBusy("upload");
    setStatus("");
    try {
      const nextUser = await uploadProfileMedia(kind, file);
      onUserUpdate(nextUser);
      setStatus("Imaginea a fost actualizată.");
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut încărca imaginea.");
    } finally {
      setBusy("");
      event.target.value = "";
    }
  };

  const remove = async () => {
    if (busy || !hasMedia) return;
    setBusy("delete");
    setStatus("");
    try {
      const nextUser = await deleteProfileMedia(kind);
      onUserUpdate(nextUser);
      setStatus("Imaginea a fost eliminată.");
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut elimina imaginea.");
    } finally {
      setBusy("");
    }
  };

  return (
    <section className={`profile-media-panel ${isProfilePhoto ? "is-profile-photo" : "is-cover-photo"} ${locked ? "locked" : ""}`}>
      <div className={`profile-media-preview ${isProfilePhoto ? "is-profile-photo" : "is-cover-photo"}`}>
        {previewUrl ? <img className={isProfilePhoto ? "profile-picture" : undefined} src={previewUrl} alt="" /> : <FiImage aria-hidden="true" />}
      </div>
      <div className="profile-media-body">
        <div className="piece-card-kicker">{title}</div>
        <p className="auth-sub">{locked && hasMedia ? "Imaginea salvată va redeveni vizibilă când abonamentul Premium este activ." : description}</p>
        {recommendation ? <p className="profile-media-suggestion">Recomandat: {recommendation}</p> : null}
        <p className="profile-media-warning">
          <FiAlertTriangle aria-hidden="true" />
          <span>Imaginile cu alte dimensiuni vor fi scalate și decupate la încărcare.</span>
        </p>
        <input ref={inputRef} className="visually-hidden" type="file" accept="image/png,image/jpeg,image/webp,image/avif" onChange={upload} disabled={locked || Boolean(busy)} />
        <div className="button-row">
          <button className="cal-btn" type="button" onClick={() => inputRef.current?.click()} disabled={locked || Boolean(busy)}>
            <FiUpload aria-hidden="true" />
            {busy === "upload" ? "Se încarcă..." : "Încarcă"}
          </button>
          {hasMedia ? (
            <button className="cal-btn" type="button" onClick={remove} disabled={locked || Boolean(busy)}>
              <FiTrash2 aria-hidden="true" />
              {busy === "delete" ? "Se elimină..." : "Elimină"}
            </button>
          ) : null}
          {locked ? <a className="cal-btn primary" href={mainPath("/premium")}>Premium</a> : null}
        </div>
        {status ? <div className={status.includes("Nu am putut") ? "inline-error" : "inline-status"}>{status}</div> : null}
      </div>
    </section>
  );
}

function promotionPostUrl(post) {
  return post?.owner?.username && post?.slug ? `${blogUrl(post.owner.username)}/${post.slug}` : "#";
}

function PromotionItem({ item, kind, promoted, busy, disabled, onToggle }) {
  const isAuthor = kind === "author";
  const title = isAuthor ? usernameHandle(item.username) : item.title;
  const meta = isAuthor ? htmlToText(item.subtitle || "") : item.owner?.username ? usernameHandle(item.owner.username) : "";
  const href = isAuthor ? blogUrl(item.username) : promotionPostUrl(item);
  return (
    <div className="promotion-item">
      <a className="promotion-item-main" href={href}>
        {isAuthor ? <img className="promotion-avatar" src={profileAvatarUrl(item, 64)} alt="" aria-hidden="true" /> : <FiBookOpen aria-hidden="true" />}
        <span>
          <strong>{title}</strong>
          {meta ? <small>{meta}</small> : null}
        </span>
      </a>
      <button className={`cal-btn ${promoted ? "" : "primary"}`.trim()} type="button" onClick={onToggle} disabled={busy || disabled}>
        <FiStar aria-hidden="true" />
        {promoted ? "Elimină" : "Promovează"}
      </button>
    </div>
  );
}

function PromotionGroup({ title, Icon, items, kind, empty, busyKey, promotedIds, limitReached, onToggle }) {
  return (
    <div className="promotion-group">
      <div className="promotion-group-head">
        <Icon aria-hidden="true" />
        <span>{title}</span>
      </div>
      {items.length ? (
        <div className="promotion-item-list">
          {items.map((item) => {
            const promoted = promotedIds.has(item.id);
            return (
              <PromotionItem
                key={`${kind}-${item.id}`}
                item={item}
                kind={kind}
                promoted={promoted}
                busy={busyKey === `${kind}-${item.id}`}
                disabled={!promoted && limitReached}
                onToggle={() => onToggle(kind, item, promoted)}
              />
            );
          })}
        </div>
      ) : <p className="auth-sub">{empty}</p>}
    </div>
  );
}

function PromotionSettingsPanel() {
  const [promotions, setPromotions] = useState(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState({ own_posts: [], authors: [], other_posts: [] });
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [busyKey, setBusyKey] = useState("");
  const [status, setStatus] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchPromotions()
      .then((data) => {
        if (!cancelled) {
          setPromotions(data);
          setStatus("");
        }
      })
      .catch((requestError) => {
        if (!cancelled) setStatus(requestError.message || "Nu am putut încărca promovările.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const term = query.trim();
    if (term.length < 2) {
      setResults({ own_posts: [], authors: [], other_posts: [] });
      setSearching(false);
      return undefined;
    }
    let cancelled = false;
    setSearching(true);
    const timer = window.setTimeout(() => {
      searchPromotions(term)
        .then((data) => {
          if (!cancelled) setResults(data);
        })
        .catch((requestError) => {
          if (!cancelled) setStatus(requestError.message || "Nu am putut căuta promovări.");
        })
        .finally(() => {
          if (!cancelled) setSearching(false);
        });
    }, 180);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [query]);

  const limits = promotions?.limits || { own_posts: 2, authors: 3, other_posts: 3 };
  const ownPostIds = new Set((promotions?.own_posts || []).map((item) => item.id));
  const authorIds = new Set((promotions?.authors || []).map((item) => item.id));
  const otherPostIds = new Set((promotions?.other_posts || []).map((item) => item.id));
  const allPostIds = new Set([...ownPostIds, ...otherPostIds]);

  const toggle = async (kind, item, promoted) => {
    const key = `${kind}-${item.id}`;
    setBusyKey(key);
    setStatus("");
    try {
      const response = kind === "author"
        ? (promoted ? await unpromoteAuthor(item.id) : await promoteAuthor(item.id))
        : (promoted ? await unpromotePost(item.id) : await promotePost(item.id));
      setPromotions(response.promotions);
      setStatus(promoted ? "Promovarea a fost eliminată." : "Promovarea a fost salvată.");
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut actualiza promovarea.");
    } finally {
      setBusyKey("");
    }
  };

  return (
    <section className="profile-settings-section promotion-settings-section">
      <div className="profile-panel-heading">
        <FiStar aria-hidden="true" />
        <div className="piece-card-kicker">promovări</div>
      </div>
      {loading ? <p className="auth-sub">Se încarcă promovările.</p> : null}
      {promotions ? (
        <div className="promotion-current-grid">
          <PromotionGroup title={`Textele tale (${promotions.own_posts.length}/${limits.own_posts})`} Icon={FiBookOpen} items={promotions.own_posts} kind="own-post" empty="Nu ai texte proprii promovate." busyKey={busyKey} promotedIds={ownPostIds} limitReached={false} onToggle={toggle} />
          <PromotionGroup title={`Autori (${promotions.authors.length}/${limits.authors})`} Icon={FiUsers} items={promotions.authors} kind="author" empty="Nu ai autori promovați." busyKey={busyKey} promotedIds={authorIds} limitReached={false} onToggle={toggle} />
          <PromotionGroup title={`Texte de la alți autori (${promotions.other_posts.length}/${limits.other_posts})`} Icon={FiBookOpen} items={promotions.other_posts} kind="other-post" empty="Nu ai texte externe promovate." busyKey={busyKey} promotedIds={otherPostIds} limitReached={false} onToggle={toggle} />
        </div>
      ) : null}
      <label className="auth-field profile-inline-label" htmlFor="promotion-search"><FiSearch aria-hidden="true" />Caută promovări</label>
      <input id="promotion-search" className="cal-input" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="titlu sau autor" />
      <div className="promotion-search-results">
        <PromotionGroup title="Textele tale" Icon={FiBookOpen} items={results.own_posts || []} kind="own-post" empty={query.trim().length < 2 ? "Scrie cel puțin 2 caractere." : searching ? "Se caută." : "Niciun text găsit."} busyKey={busyKey} promotedIds={allPostIds} limitReached={(promotions?.own_posts?.length || 0) >= limits.own_posts} onToggle={toggle} />
        <PromotionGroup title="Autori" Icon={FiUsers} items={results.authors || []} kind="author" empty={query.trim().length < 2 ? "Scrie cel puțin 2 caractere." : searching ? "Se caută." : "Niciun autor găsit."} busyKey={busyKey} promotedIds={authorIds} limitReached={(promotions?.authors?.length || 0) >= limits.authors} onToggle={toggle} />
        <PromotionGroup title="Texte de la alți autori" Icon={FiBookOpen} items={results.other_posts || []} kind="other-post" empty={query.trim().length < 2 ? "Scrie cel puțin 2 caractere." : searching ? "Se caută." : "Niciun text găsit."} busyKey={busyKey} promotedIds={allPostIds} limitReached={(promotions?.other_posts?.length || 0) >= limits.other_posts} onToggle={toggle} />
      </div>
      {status ? <div className={status.includes("Nu am putut") || status.includes("Poți") ? "inline-error" : "inline-status"}>{status}</div> : null}
    </section>
  );
}

function ProfileSettingsView({ user, onUserUpdate }) {
  const [form, setForm] = useState(() => profileFormFromUser(user));
  const [emailPrefs, setEmailPrefs] = useState(() => emailPrefsFromUser(user));
  const [stafetaParticipates, setStafetaParticipates] = useState(Boolean(user?.stafeta_participates));
  const [stafetaSlots, setStafetaSlots] = useState(Number(user?.stafeta_desired_slots || user?.stafeta_max_slots || 3));
  const [status, setStatus] = useState("");
  const [emailStatus, setEmailStatus] = useState("");
  const [stafetaStatus, setStafetaStatus] = useState("");
  const [savingEmailPrefs, setSavingEmailPrefs] = useState(false);
  const [savingStafeta, setSavingStafeta] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setForm(profileFormFromUser(user));
    setEmailPrefs(emailPrefsFromUser(user));
    setStafetaParticipates(Boolean(user?.stafeta_participates));
    setStafetaSlots(Number(user?.stafeta_desired_slots || user?.stafeta_max_slots || 3));
  }, [user?.id, user?.stafeta_participates, user?.stafeta_desired_slots, user?.stafeta_max_slots]);

  if (!user) return <AuthRequired />;

  const supportLinksLocked = !(user.is_premium && SUPPORT_LINK_PREMIUM_TIERS.has(user.premium_tier || "free"));

  const setField = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }));
  };
  const setEmailField = (field, value) => {
    setEmailPrefs((current) => ({ ...current, [field]: value }));
  };

  const saveEmailPreferences = async () => {
    if (savingEmailPrefs) return;
    setSavingEmailPrefs(true);
    setEmailStatus("");
    try {
      const nextPrefs = await updateEmailPreferences(emailPrefs);
      setEmailPrefs(nextPrefs);
      onUserUpdate({ ...user, ...nextPrefs });
      setEmailStatus("Preferințele de email au fost salvate.");
    } catch (requestError) {
      setEmailStatus(requestError.message || "Nu am putut salva preferințele de email.");
    } finally {
      setSavingEmailPrefs(false);
    }
  };

  const saveStafetaParticipation = async (nextValue, nextSlots = stafetaSlots) => {
    if (savingStafeta) return;
    const maxSlots = Number(user?.stafeta_max_slots || 3);
    const normalizedSlots = nextValue ? Math.min(Math.max(1, Number(nextSlots) || maxSlots), maxSlots) : 0;
    setSavingStafeta(true);
    setStafetaStatus("");
    setStafetaParticipates(nextValue);
    if (nextValue) setStafetaSlots(normalizedSlots);
    try {
      const result = await updateStafetaParticipation(nextValue, normalizedSlots);
      const participates = Boolean(result?.participates);
      const desiredSlots = Number(result?.desired_slots || result?.max_slots || maxSlots);
      setStafetaParticipates(participates);
      setStafetaSlots(desiredSlots);
      onUserUpdate({
        ...user,
        stafeta_participates: participates,
        stafeta_desired_slots: desiredSlots,
        stafeta_max_slots: Number(result?.max_slots || maxSlots),
        stafeta_open_assignments: Number(result?.open_assignments || 0)
      });
      setStafetaStatus(participates ? `Participarea la Ștafeta este activă pentru ${formatNumber(desiredSlots)} texte.` : "Participarea la Ștafeta este oprită.");
    } catch (requestError) {
      setStafetaParticipates(Boolean(user?.stafeta_participates));
      setStafetaSlots(Number(user?.stafeta_desired_slots || user?.stafeta_max_slots || 3));
      setStafetaStatus(requestError.message || "Nu am putut salva participarea la Ștafeta.");
    } finally {
      setSavingStafeta(false);
    }
  };

  const submit = async (event) => {
    event.preventDefault();
    setStatus("");
    if (htmlToText(form.subtitle).length > PROFILE_DESCRIPTION_CHARACTER_LIMIT) {
      setStatus(`Descrierea poate avea cel mult ${formatNumber(PROFILE_DESCRIPTION_CHARACTER_LIMIT)} de caractere.`);
      return;
    }
    setSaving(true);
    try {
      const nextForm = supportLinksLocked
        ? {
            ...form,
            ...Object.fromEntries(SUPPORT_PROFILE_LINKS.map(({ field }) => [field, ""]))
          }
        : form;
      const nextUser = await updateProfileSettings(nextForm);
      onUserUpdate(nextUser);
      setForm(profileFormFromUser(nextUser));
      setStatus("Profilul a fost salvat.");
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut salva profilul.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <PageShell kicker="profil" title="Profilul tău" sub="Actualizează prezentarea publică, linkurile și imaginile profilului.">
      <form className="profile-settings-form" onSubmit={submit}>
        <section className="profile-settings-section">
          <div className="profile-panel-heading">
            <FiMapPin aria-hidden="true" />
            <div className="piece-card-kicker">prezentare</div>
          </div>
          <label className="auth-field" htmlFor="profile-subtitle">Descriere</label>
          <RichTextEditor id="profile-subtitle" className="compact" value={form.subtitle} onChange={(value) => setField("subtitle", value)} maxLength={PROFILE_DESCRIPTION_CHARACTER_LIMIT} />
          <label className="auth-field profile-inline-label" htmlFor="profile-location"><FiMapPin aria-hidden="true" />Locație</label>
          <input id="profile-location" className="cal-input" value={form.location} onChange={(event) => setField("location", event.target.value)} maxLength="120" />
          <label className="auth-field profile-inline-label" htmlFor="profile-youtube"><SiYoutube aria-hidden="true" />Playlist YouTube</label>
          <input id="profile-youtube" className="cal-input" type="text" inputMode="url" autoCapitalize="none" autoCorrect="off" value={form.youtube_playlist_url} onChange={(event) => setField("youtube_playlist_url", event.target.value)} placeholder="youtube.com/playlist?list=..." />
        </section>
        <section className="profile-settings-section">
          <div className="profile-panel-heading">
            <FiImage aria-hidden="true" />
            <div className="piece-card-kicker">copertă</div>
          </div>
          <CoverChoiceField username={user.username} selectedSeed={form.cover_seed} onChange={(seed) => setField("cover_seed", seed)} />
        </section>
        <section className="profile-settings-section">
          <div className="profile-panel-heading">
            <FiExternalLink aria-hidden="true" />
            <div className="piece-card-kicker">linkuri sociale</div>
          </div>
          <div className="profile-field-grid">
            {SOCIAL_PROFILE_LINKS.map(({ field, label, Icon, className }) => (
              <label className={`profile-field ${className || ""}`.trim()} key={field}>
                <span className="profile-field-label"><Icon aria-hidden="true" />{label}</span>
                <input className="cal-input" type="text" inputMode="url" autoCapitalize="none" autoCorrect="off" value={form[field]} onChange={(event) => setField(field, event.target.value)} />
              </label>
            ))}
          </div>
        </section>
        <section className="profile-settings-section">
          <div className="profile-panel-heading">
            <FiHeart aria-hidden="true" />
            <div className="piece-card-kicker">donații</div>
          </div>
          {supportLinksLocked ? (
            <div className="profile-support-lock">
              <p className="auth-sub">Linkurile PayPal, Patreon și Cafea sunt disponibile pentru utilizatorii Premium.</p>
              <a className="cal-btn primary" href={mainPath("/premium")}>Premium</a>
            </div>
          ) : null}
          <div className="profile-field-grid">
            {SUPPORT_PROFILE_LINKS.map(({ field, label, Icon, className }) => (
              <label className={`profile-field ${className || ""}`.trim()} key={field}>
                <span className="profile-field-label"><Icon aria-hidden="true" />{label}</span>
                <input className="cal-input" type="text" inputMode="url" autoCapitalize="none" autoCorrect="off" value={form[field]} onChange={(event) => setField(field, event.target.value)} disabled={supportLinksLocked} />
              </label>
            ))}
          </div>
        </section>
        <div className="button-row">
          <button className="cal-btn primary" type="submit" disabled={saving}>{saving ? "Se salvează..." : "Salvează profilul"}</button>
          <a className="cal-btn" href={blogUrl(user.username)}>Vezi profilul public</a>
        </div>
        {status ? <div className={status.includes("Nu am putut") || status.includes("cel mult") ? "inline-error" : "inline-status"}>{status}</div> : null}
      </form>
      <PromotionSettingsPanel />
      <section className="profile-settings-section email-preferences-section">
        <div className="profile-panel-heading">
          <FiUsers aria-hidden="true" />
          <div className="piece-card-kicker">Ștafeta</div>
        </div>
        <div className="email-preference-grid">
          <label className="email-preference-toggle">
            <input
              type="checkbox"
              checked={stafetaParticipates}
              onChange={(event) => saveStafetaParticipation(event.target.checked, event.target.checked ? stafetaSlots || user?.stafeta_max_slots || 3 : 0)}
              disabled={savingStafeta}
            />
            <span>Particip la Ștafeta</span>
          </label>
          <label className="profile-field">
            <span className="profile-field-label">Număr Ștafete</span>
            <select className="cal-input" value={stafetaParticipates ? stafetaSlots : 0} onChange={(event) => saveStafetaParticipation(true, Number(event.target.value))} disabled={savingStafeta || !stafetaParticipates}>
              {!stafetaParticipates ? <option value={0}>0</option> : null}
              {stafetaSlotOptions(user?.stafeta_max_slots || 3).map((value) => (
                <option value={value} key={value}>{value}</option>
              ))}
            </select>
          </label>
        </div>
        <p className="muted">Active: {formatNumber(user?.stafeta_open_assignments || 0)} / {formatNumber(stafetaParticipates ? stafetaSlots : user?.stafeta_max_slots || 3)}</p>
        {stafetaStatus ? <div className={stafetaStatus.includes("Nu am putut") ? "inline-error" : "inline-status"}>{stafetaStatus}</div> : null}
      </section>
      <section className="profile-settings-section email-preferences-section">
        <div className="profile-panel-heading">
          <FiMail aria-hidden="true" />
          <div className="piece-card-kicker">email</div>
        </div>
        <div className="email-preference-grid">
          {EMAIL_PREFERENCE_OPTIONS.map(([field, label]) => (
            <label className="email-preference-toggle" key={field}>
              <input
                type="checkbox"
                checked={Boolean(emailPrefs[field])}
                onChange={(event) => setEmailField(field, event.target.checked)}
              />
              <span>{label}</span>
            </label>
          ))}
        </div>
        <div className="button-row">
          <button className="cal-btn" type="button" disabled={savingEmailPrefs} onClick={saveEmailPreferences}>
            {savingEmailPrefs ? "Se salvează..." : "Salvează emailurile"}
          </button>
        </div>
        {emailStatus ? <div className={emailStatus.includes("Nu am putut") ? "inline-error" : "inline-status"}>{emailStatus}</div> : null}
      </section>
      <div className="profile-media-grid">
        <ProfileMediaPanel
          user={user}
          kind="profil"
          title="fotografie profil"
          description="Imagine pătrată pentru profilul public."
          previewUrl={user.profile_photo_url || profileAvatarUrl(user)}
          hasMedia={Boolean(user.has_profile_photo)}
          onUserUpdate={onUserUpdate}
        />
        <ProfileMediaPanel
          user={user}
          kind="coperta"
          title="copertă profil"
          description="Imagine lată pentru antetul profilului public."
          previewUrl={user.cover_photo_url || profileCoverUrl(user)}
          hasMedia={Boolean(user.has_cover_photo)}
          onUserUpdate={onUserUpdate}
        />
      </div>
    </PageShell>
  );
}

export default function ProfileSettingsRoute({ user, onUserUpdate }) {
  return <ProfileSettingsView user={user} onUserUpdate={onUserUpdate} />;
}
