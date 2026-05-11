import { useEffect, useMemo, useState } from "react";
import { SiFacebook, SiGoogle } from "react-icons/si";
import {
  AUTH_FACEBOOK_PATH,
  AUTH_GOOGLE_PATH,
  activatePasswordSignup,
  completeAuthSetup,
  confirmPasswordReset,
  loginWithPassword,
  registerWithPassword,
  requestPasswordReset,
  resendActivationCode
} from "../api/auth.js";
import { AUTH_AVATAR_OPTIONS, AUTH_COVER_OPTIONS, PROFILE_DESCRIPTION_CHARACTER_LIMIT } from "../app/constants.js";
import { RichTextEditor } from "../app/editor.jsx";
import { formatNumber, htmlToText } from "../app/format.js";
import { PageShell } from "../app/layout.jsx";
import { avatarPreviewUrl, blogUrl, coverPreviewUrl, mainPath } from "../app/paths.js";

function AuthHomeView() {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [status, setStatus] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [flowEmail, setFlowEmail] = useState("");
  const emailForCode = flowEmail || email.trim();

  const title = useMemo(() => {
    if (mode === "register") return "Creează cont";
    if (mode === "activate") return "Activează contul";
    if (mode === "reset") return "Resetare parolă";
    if (mode === "resetConfirm") return "Cod resetare";
    return "Autentificare";
  }, [mode]);

  const setNextMode = (nextMode) => {
    setMode(nextMode);
    setStatus("");
    setCode("");
  };

  const submitLogin = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setStatus("");
    try {
      const response = await loginWithPassword({ email, password });
      window.location.href = response.redirect_url || mainPath("/");
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut autentifica acest cont.");
      setSubmitting(false);
    }
  };

  const submitRegister = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setStatus("");
    try {
      const response = await registerWithPassword({ email, password });
      setFlowEmail(response.email || email.trim());
      setPassword("");
      setMode("activate");
      setStatus(response.message || "Ți-am trimis codul de activare.");
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut crea contul.");
    } finally {
      setSubmitting(false);
    }
  };

  const submitActivation = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setStatus("");
    try {
      const response = await activatePasswordSignup({ email: emailForCode, code });
      window.location.href = response.setup_url || mainPath("/autentificare/configurare");
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut activa contul.");
      setSubmitting(false);
    }
  };

  const resendCode = async () => {
    if (!emailForCode) return;
    setSubmitting(true);
    setStatus("");
    try {
      const response = await resendActivationCode({ email: emailForCode });
      setStatus(response.message || "Ți-am trimis un cod nou.");
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut retrimite codul.");
    } finally {
      setSubmitting(false);
    }
  };

  const submitResetRequest = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setStatus("");
    try {
      const response = await requestPasswordReset({ email });
      setFlowEmail(response.email || email.trim());
      setPassword("");
      setMode("resetConfirm");
      setStatus(response.message || "Dacă adresa există, vei primi un cod.");
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut porni resetarea.");
    } finally {
      setSubmitting(false);
    }
  };

  const submitResetConfirm = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setStatus("");
    try {
      const response = await confirmPasswordReset({ email: emailForCode, code, password });
      window.location.href = response.redirect_url || mainPath("/");
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut seta parola.");
      setSubmitting(false);
    }
  };

  const renderPasswordFields = (withEmail = true, withCode = false, passwordLabel = "Parolă", withPassword = true) => (
    <>
      {withEmail ? (
        <>
          <label className="auth-field" htmlFor="auth-email">Email</label>
          <input id="auth-email" className="cal-input" type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" required />
        </>
      ) : (
        <p className="auth-sub auth-flow-email">{emailForCode}</p>
      )}
      {withCode ? (
        <>
          <label className="auth-field" htmlFor="auth-code">Cod</label>
          <input id="auth-code" className="cal-input auth-code-input" inputMode="numeric" pattern="[0-9]*" value={code} onChange={(event) => setCode(event.target.value)} autoComplete="one-time-code" required />
        </>
      ) : null}
      {withPassword && mode !== "activate" ? (
        <>
          <label className="auth-field" htmlFor="auth-password">{passwordLabel}</label>
          <input id="auth-password" className="cal-input" type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete={mode === "login" ? "current-password" : "new-password"} required minLength={mode === "login" ? undefined : 10} maxLength={128} />
        </>
      ) : null}
    </>
  );

  return (
    <PageShell kicker="cont" title={title} sub="Intră în cont cu email, Google sau Facebook.">
      <div className="auth-panel">
        <div className="auth-provider-row">
          <a className="cal-btn auth-provider" href={AUTH_GOOGLE_PATH}><SiGoogle aria-hidden="true" /> Google</a>
          <a className="cal-btn auth-provider facebook" href={AUTH_FACEBOOK_PATH}><SiFacebook aria-hidden="true" /> Facebook</a>
        </div>

        {mode === "login" ? (
          <form className="form-stack auth-form" onSubmit={submitLogin}>
            {renderPasswordFields(true, false)}
            {status ? <div className="inline-error">{status}</div> : null}
            <button className="cal-btn primary" type="submit" disabled={submitting}>{submitting ? "Se autentifică..." : "Intră în cont"}</button>
          </form>
        ) : null}

        {mode === "register" ? (
          <form className="form-stack auth-form" onSubmit={submitRegister}>
            {renderPasswordFields(true, false)}
            {status ? <div className="inline-error">{status}</div> : null}
            <button className="cal-btn primary" type="submit" disabled={submitting}>{submitting ? "Se trimite..." : "Trimite codul"}</button>
          </form>
        ) : null}

        {mode === "activate" ? (
          <form className="form-stack auth-form" onSubmit={submitActivation}>
            {renderPasswordFields(false, true)}
            {status ? <div className="inline-error">{status}</div> : null}
            <div className="button-row">
              <button className="cal-btn primary" type="submit" disabled={submitting}>{submitting ? "Se verifică..." : "Activează"}</button>
              <button className="cal-btn" type="button" onClick={resendCode} disabled={submitting}>Retrimite cod</button>
            </div>
          </form>
        ) : null}

        {mode === "reset" ? (
          <form className="form-stack auth-form" onSubmit={submitResetRequest}>
            {renderPasswordFields(true, false, "Parolă", false)}
            {status ? <div className="inline-error">{status}</div> : null}
            <button className="cal-btn primary" type="submit" disabled={submitting}>{submitting ? "Se trimite..." : "Trimite codul"}</button>
          </form>
        ) : null}

        {mode === "resetConfirm" ? (
          <form className="form-stack auth-form" onSubmit={submitResetConfirm}>
            {renderPasswordFields(false, true, "Parolă nouă")}
            {status ? <div className="inline-error">{status}</div> : null}
            <button className="cal-btn primary" type="submit" disabled={submitting}>{submitting ? "Se salvează..." : "Setează parola"}</button>
          </form>
        ) : null}

        <div className="auth-mode-grid" aria-label="Opțiuni cont">
          <button className={mode === "login" ? "active" : ""} type="button" onClick={() => setNextMode("login")}>Login</button>
          <button className={mode === "register" ? "active" : ""} type="button" onClick={() => setNextMode("register")}>Cont nou</button>
          <button className={mode === "reset" || mode === "resetConfirm" ? "active" : ""} type="button" onClick={() => setNextMode("reset")}>Parolă uitată</button>
        </div>
      </div>
    </PageShell>
  );
}

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
      window.location.href = blogUrl(response.username);
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

export default function AuthRoute({ route }) {
  if (route.name === "authLogin") return <AuthHomeView />;
  if (route.name === "authCallback") return <AuthCallbackView />;
  return <AuthSetupView />;
}
