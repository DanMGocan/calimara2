import { useEffect, useRef, useState } from "react";
import { FiAlertTriangle, FiExternalLink, FiHeart, FiImage, FiMapPin, FiTrash2, FiUpload } from "react-icons/fi";
import { SiYoutube } from "react-icons/si";
import { deleteProfileMedia, updateProfileSettings, uploadProfileMedia } from "../api/users.js";
import { AUTH_COVER_OPTIONS, PROFILE_DESCRIPTION_CHARACTER_LIMIT } from "../app/constants.js";
import { RichTextEditor } from "../app/editor.jsx";
import { formatNumber, htmlToText } from "../app/format.js";
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
function ProfileSettingsView({ user, onUserUpdate }) {
  const [form, setForm] = useState(() => profileFormFromUser(user));
  const [status, setStatus] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setForm(profileFormFromUser(user));
  }, [user?.id]);

  if (!user) return <AuthRequired />;

  const setField = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }));
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
      const nextUser = await updateProfileSettings(form);
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
          <input id="profile-youtube" className="cal-input" type="url" value={form.youtube_playlist_url} onChange={(event) => setField("youtube_playlist_url", event.target.value)} placeholder="https://www.youtube.com/playlist?list=..." />
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
                <input className="cal-input" type="url" value={form[field]} onChange={(event) => setField(field, event.target.value)} />
              </label>
            ))}
          </div>
        </section>
        <section className="profile-settings-section">
          <div className="profile-panel-heading">
            <FiHeart aria-hidden="true" />
            <div className="piece-card-kicker">donații</div>
          </div>
          <div className="profile-field-grid">
            {SUPPORT_PROFILE_LINKS.map(({ field, label, Icon, className }) => (
              <label className={`profile-field ${className || ""}`.trim()} key={field}>
                <span className="profile-field-label"><Icon aria-hidden="true" />{label}</span>
                <input className="cal-input" type="url" value={form[field]} onChange={(event) => setField(field, event.target.value)} />
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
