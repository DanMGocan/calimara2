import { useEffect, useState } from "react";
import { completeAuthSetup } from "../api/auth.js";
import { AUTH_AVATAR_OPTIONS, AUTH_COVER_OPTIONS, PROFILE_DESCRIPTION_CHARACTER_LIMIT } from "../app/constants.js";
import { RichTextEditor } from "../app/editor.jsx";
import { formatNumber, htmlToText } from "../app/format.js";
import { PageShell } from "../app/layout.jsx";
import { avatarPreviewUrl, blogUrl, coverPreviewUrl, mainPath } from "../app/paths.js";

function AuthSetupView() {
  const [username, setUsername] = useState("");
  const [subtitle, setSubtitle] = useState("");
  const [avatarChoice, setAvatarChoice] = useState(AUTH_AVATAR_OPTIONS[0].key);
  const [coverChoice, setCoverChoice] = useState(AUTH_COVER_OPTIONS[0].key);
  const [status, setStatus] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const usernameSeed = username.trim().toLowerCase() || "calimara";
  const avatarSeed = `${usernameSeed}-${avatarChoice}`;
  const coverSeed = `${usernameSeed}-cover-${coverChoice}`;

  const submit = async (event) => {
    event.preventDefault();
    const trimmedUsername = username.trim();
    setSubmitting(true);
    setStatus("");
    if (htmlToText(subtitle).length > PROFILE_DESCRIPTION_CHARACTER_LIMIT) {
      setStatus(`Descrierea poate avea cel mult ${formatNumber(PROFILE_DESCRIPTION_CHARACTER_LIMIT)} de caractere.`);
      setSubmitting(false);
      return;
    }
    try {
      const response = await completeAuthSetup({
        username: trimmedUsername,
        subtitle: subtitle.trim(),
        avatar_seed: avatarSeed,
        cover_seed: coverSeed
      });
      window.location.href = response.redirect_url || blogUrl(response.username);
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut finaliza contul.");
      setSubmitting(false);
    }
  };

  return (
    <PageShell kicker="cont" title="Configurează contul" sub="Alege numele public, descrierea și avatarul blogului tău.">
      <form className="form-stack" onSubmit={submit}>
        <label className="auth-field" htmlFor="setup-username">Nume blog</label>
        <input id="setup-username" className="cal-input" value={username} onChange={(event) => setUsername(event.target.value)} required pattern="[A-Za-z0-9]+" />
        <label className="auth-field" htmlFor="setup-subtitle">Descriere</label>
        <RichTextEditor id="setup-subtitle" className="compact" value={subtitle} onChange={setSubtitle} maxLength={PROFILE_DESCRIPTION_CHARACTER_LIMIT} />
        <fieldset className="avatar-choice-field">
          <legend className="auth-field">Avatar</legend>
          <div className="avatar-choice-grid">
            {AUTH_AVATAR_OPTIONS.map((option) => {
              const seed = `${usernameSeed}-${option.key}`;
              const selected = avatarChoice === option.key;
              return (
                <button
                  key={option.key}
                  className={`avatar-choice${selected ? " selected" : ""}`}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => setAvatarChoice(option.key)}
                >
                  <img className="profile-picture" src={avatarPreviewUrl(seed)} alt="" aria-hidden="true" />
                  <span>{option.label}</span>
                </button>
              );
            })}
          </div>
        </fieldset>
        <fieldset className="cover-choice-field">
          <legend className="auth-field">Copertă</legend>
          <div className="cover-choice-grid">
            {AUTH_COVER_OPTIONS.map((option) => {
              const seed = `${usernameSeed}-cover-${option.key}`;
              const selected = coverChoice === option.key;
              return (
                <button
                  key={option.key}
                  className={`cover-choice${selected ? " selected" : ""}`}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => setCoverChoice(option.key)}
                >
                  <img src={coverPreviewUrl(seed, 640)} alt="" aria-hidden="true" />
                  <span>{option.label}</span>
                </button>
              );
            })}
          </div>
        </fieldset>
        {status ? <div className="inline-error">{status}</div> : null}
        <button className="cal-btn primary" type="submit" disabled={submitting}>{submitting ? "Se salvează..." : "Finalizează"}</button>
      </form>
    </PageShell>
  );
}

function AuthCallbackView() {
  const callbackStatus = new URLSearchParams(window.location.search).get("status");

  useEffect(() => {
    if (callbackStatus === "setup") {
      window.location.replace(mainPath("/autentificare/configurare"));
    }
  }, [callbackStatus]);

  if (callbackStatus === "setup") {
    return <PageShell kicker="cont" title="Configurează contul" sub="Pregătim formularul pentru blogul tău." />;
  }

  return (
    <PageShell kicker="cont" title="Autentificare finalizată" sub="Sesiunea a fost actualizată.">
      <a className="cal-btn primary" href={mainPath("/")}>Continuă</a>
    </PageShell>
  );
}

function AuthLoginRemovedView() {
  return <PageShell kicker="cont" title="Autentificare" sub="Deschidem fereastra de autentificare." />;
}

export default function AuthRoute({ route }) {
  if (route.name === "authLogin") return <AuthLoginRemovedView />;
  if (route.name === "authCallback") return <AuthCallbackView />;
  return <AuthSetupView />;
}
