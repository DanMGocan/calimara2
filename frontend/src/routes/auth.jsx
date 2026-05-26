import { useEffect, useState } from "react";
import { FaFacebookF, FaGoogle } from "react-icons/fa";
import { AUTH_FACEBOOK_PATH, AUTH_GOOGLE_PATH, addSetupDiacritics, completeAuthSetup, fetchInvitation, loginWithInvitationPassword } from "../api/auth.js";
import { AUTH_AVATAR_OPTIONS, AUTH_COVER_OPTIONS, PROFILE_DESCRIPTION_CHARACTER_LIMIT } from "../app/constants.js";
import { DiacriticsProgressOverlay, DiacriticsReviewPanel, useDiacriticsProgress } from "../app/diacritics.jsx";
import { RichTextEditor } from "../app/editor.jsx";
import { formatNumber, htmlToText } from "../app/format.js";
import { PageShell } from "../app/layout.jsx";
import { avatarPreviewUrl, blogUrl, coverPreviewUrl, mainPath } from "../app/paths.js";

const INVITE_TIER_LABELS = {
  free: "Gratuit",
  trubadur: "Trubadur",
  cronicar: "Cronicar",
  rapsod: "Rapsod"
};

function providerHref(path, returnTo) {
  if (!returnTo) return path;
  const query = new URLSearchParams({ return_to: returnTo });
  return `${path}?${query.toString()}`;
}

function inviteTierLabel(tier) {
  return INVITE_TIER_LABELS[tier] || tier || INVITE_TIER_LABELS.free;
}

function GeneratedChoicePreview({ kind, src }) {
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [src]);

  if (failed) {
    return (
      <span className={`generated-choice-fallback ${kind}`} aria-hidden="true">
        <span>{kind === "avatar" ? "C" : ""}</span>
      </span>
    );
  }

  return (
    <img
      className={kind === "avatar" ? "profile-picture" : undefined}
      src={src}
      alt=""
      aria-hidden="true"
      onError={() => setFailed(true)}
      onLoad={(event) => {
        if (!event.currentTarget.naturalWidth) setFailed(true);
      }}
    />
  );
}

function AuthSetupView() {
  const [username, setUsername] = useState("");
  const [subtitle, setSubtitle] = useState("");
  const [avatarChoice, setAvatarChoice] = useState(AUTH_AVATAR_OPTIONS[0].key);
  const [coverChoice, setCoverChoice] = useState(AUTH_COVER_OPTIONS[0].key);
  const [acceptLegal, setAcceptLegal] = useState(false);
  const [autoDiacritics, setAutoDiacritics] = useState(false);
  const [diacriticsReview, setDiacriticsReview] = useState(null);
  const [status, setStatus] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const selectedAvatarOption = AUTH_AVATAR_OPTIONS.find((option) => option.key === avatarChoice) || AUTH_AVATAR_OPTIONS[0];
  const selectedCoverOption = AUTH_COVER_OPTIONS.find((option) => option.key === coverChoice) || AUTH_COVER_OPTIONS[0];
  const avatarSeed = selectedAvatarOption.seed;
  const coverSeed = selectedCoverOption.seed;
  const subtitleText = htmlToText(subtitle);
  const canReviewDescription = Boolean(autoDiacritics && subtitleText && !diacriticsReview);
  const {
    diacriticsProgress,
    startDiacriticsProgress,
    finishDiacriticsProgress,
    failDiacriticsProgress
  } = useDiacriticsProgress();

  const setDescription = (value) => {
    if (diacriticsReview) setDiacriticsReview(null);
    setSubtitle(value);
  };

  const submitLabel = () => {
    if (submitting) return canReviewDescription ? "Se adaugă diacritice..." : "Se salvează...";
    if (canReviewDescription) return "Verifică diacriticele";
    return "Finalizează";
  };

  const submit = async (event, { skipDiacritics = false } = {}) => {
    event?.preventDefault();
    const trimmedUsername = username.trim();
    if (submitting) return;
    setStatus("");
    if (subtitleText.length > PROFILE_DESCRIPTION_CHARACTER_LIMIT) {
      setStatus(`Descrierea poate avea cel mult ${formatNumber(PROFILE_DESCRIPTION_CHARACTER_LIMIT)} de caractere.`);
      return;
    }
    setSubmitting(true);
    if (!skipDiacritics && canReviewDescription) {
      try {
        startDiacriticsProgress({ content: subtitle });
        const converted = await addSetupDiacritics({ kind: "profile_description", content: subtitle });
        finishDiacriticsProgress();
        setSubtitle(converted.content ?? subtitle);
        setDiacriticsReview({
          originalSubtitle: subtitle,
          changed: converted.changed
        });
        setStatus("Am pregătit descrierea cu diacritice. Verifică textul, apoi finalizează configurarea.");
      } catch (requestError) {
        failDiacriticsProgress();
        setStatus(requestError.message || "Nu am putut adăuga diacriticele.");
      } finally {
        setSubmitting(false);
      }
      return;
    }
    if (!acceptLegal) {
      setStatus("Pentru a crea blogul, trebuie să accepți Termenii și condițiile și Politica de confidențialitate.");
      setSubmitting(false);
      return;
    }
    try {
      const response = await completeAuthSetup({
        username: trimmedUsername,
        subtitle: subtitle.trim(),
        avatar_seed: avatarSeed,
        cover_seed: coverSeed,
        accept_terms_and_privacy: acceptLegal
      });
      window.location.href = response.redirect_url || blogUrl(response.username);
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut finaliza contul.");
      setSubmitting(false);
    }
  };

  return (
    <PageShell kicker="cont" title="Configurează contul" sub="Alege numele public, descrierea și avatarul blogului tău.">
      <DiacriticsProgressOverlay {...diacriticsProgress} />
      <form className="form-stack" onSubmit={submit} autoComplete="off">
        <label className="auth-field" htmlFor="setup-username">Nume blog</label>
        <input
          id="setup-username"
          className="cal-input"
          name="blog_name"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          required
          pattern="[A-Za-z0-9]+"
          autoComplete="nickname"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck="false"
        />
        <label className="auth-field" htmlFor="setup-subtitle">Descriere</label>
        <RichTextEditor id="setup-subtitle" className="compact" value={subtitle} onChange={setDescription} maxLength={PROFILE_DESCRIPTION_CHARACTER_LIMIT} />
        <div className="field-counter" aria-live="polite">
          {formatNumber(subtitleText.length)} / {formatNumber(PROFILE_DESCRIPTION_CHARACTER_LIMIT)} caractere
        </div>
        <label className="diacritics-control">
          <input
            type="checkbox"
            checked={autoDiacritics}
            disabled={Boolean(diacriticsReview)}
            onChange={(event) => {
              setAutoDiacritics(event.target.checked);
              setDiacriticsReview(null);
            }}
          />
          <span>Adaugă automat diacritice în descriere?</span>
        </label>
        <p className="diacritics-note">Dacă bifezi opțiunea, descrierea este verificată înainte de crearea blogului.</p>
        <DiacriticsReviewPanel
          active={Boolean(diacriticsReview)}
          changed={Boolean(diacriticsReview?.changed)}
          onReset={diacriticsReview ? () => {
            setSubtitle(diacriticsReview.originalSubtitle);
            setDiacriticsReview(null);
          } : null}
        />
        <p className="auth-sub">Imaginea de profil și coperta pot fi modificate ulterior din setările profilului.</p>
        <fieldset className="avatar-choice-field">
          <legend className="auth-field">Avatar</legend>
          <div className="avatar-choice-grid">
            {AUTH_AVATAR_OPTIONS.map((option) => {
              const selected = avatarChoice === option.key;
              return (
                <button
                  key={option.key}
                  className={`avatar-choice${selected ? " selected" : ""}`}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => setAvatarChoice(option.key)}
                >
                  <GeneratedChoicePreview kind="avatar" src={avatarPreviewUrl(option.seed)} />
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
              const selected = coverChoice === option.key;
              return (
                <button
                  key={option.key}
                  className={`cover-choice${selected ? " selected" : ""}`}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => setCoverChoice(option.key)}
                >
                  <GeneratedChoicePreview kind="cover" src={coverPreviewUrl(option.seed, 640)} />
                  <span>{option.label}</span>
                </button>
              );
            })}
          </div>
        </fieldset>
        <label className="auth-legal-consent">
          <input type="checkbox" checked={acceptLegal} onChange={(event) => setAcceptLegal(event.target.checked)} />
          <span>
            Bifând, confirm că am citit și accept <a href={mainPath("/termeni")} target="_blank" rel="noreferrer">Termenii și condițiile</a> și{" "}
            <a href={mainPath("/confidentialitate")} target="_blank" rel="noreferrer">Politica de confidențialitate</a>.
          </span>
        </label>
        {status ? <div className={status.startsWith("Am pregătit") ? "inline-status" : "inline-error"}>{status}</div> : null}
        <div className="button-row">
          <button className="cal-btn primary" type="submit" disabled={submitting}>{submitLabel()}</button>
          {canReviewDescription ? (
            <button className="cal-btn" type="button" onClick={() => submit(null, { skipDiacritics: true })} disabled={submitting}>
              Finalizează fără Diacritice
            </button>
          ) : null}
        </div>
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

function InvitationView({ route, user }) {
  const token = route.token || "";
  const [loading, setLoading] = useState(true);
  const [invitation, setInvitation] = useState(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchInvitation(token)
      .then((response) => {
        if (cancelled) return;
        const nextInvitation = response.invitation || null;
        setInvitation(nextInvitation);
        setEmail(nextInvitation?.email || "");
        setStatus("");
      })
      .catch((requestError) => {
        if (!cancelled) setStatus(requestError.message || "Invitația nu a putut fi încărcată.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  useEffect(() => {
    if (invitation?.status === "accepted" && user?.username) {
      window.location.replace(blogUrl(user.username));
    }
  }, [invitation?.status, user?.username]);

  const submitPassword = async (event) => {
    event.preventDefault();
    if (submitting || !email.trim() || !password) return;
    setSubmitting(true);
    setStatus("");
    try {
      const response = await loginWithInvitationPassword({ token, email, password });
      window.location.href = response.setup_url || mainPath("/autentificare/configurare");
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut verifica invitația.");
      setSubmitting(false);
    }
  };

  if (loading) {
    return <PageShell kicker="invitație" title="Se verifică invitația" sub="Încărcăm detaliile accesului tău." />;
  }

  if (!invitation) {
    return (
      <PageShell kicker="invitație" title="Invitație indisponibilă" sub={status || "Linkul nu este valid."}>
        <a className="cal-btn" href={mainPath("/")}>Înapoi la Călimara</a>
      </PageShell>
    );
  }

  if (invitation.status !== "pending") {
    if (invitation.status === "accepted" && user?.username) {
      return <PageShell kicker="invitație" title="Invitație acceptată" sub="Te trimitem către Călimara ta." />;
    }
    const title = invitation.status === "accepted" ? "Invitație acceptată" : invitation.status === "expired" ? "Invitație expirată" : "Invitație revocată";
    const copy = invitation.status === "accepted"
      ? "Această invitație a fost deja folosită."
      : "Cere administratorului o invitație nouă.";
    return (
      <PageShell kicker="invitație" title={title} sub={copy}>
        <a className="cal-btn" href={mainPath("/")}>Înapoi la Călimara</a>
      </PageShell>
    );
  }

  const returnTo = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  const hasPremium = invitation.premium_tier && invitation.premium_tier !== "free";

  return (
    <PageShell kicker="invitație" title="Acceptă invitația" sub="Intră cu emailul invitat și creează-ți Călimara.">
      <div className="invite-panel">
        <div className="inline-status">
          Invitație pentru <strong>{invitation.email}</strong>
          {hasPremium ? <> · {inviteTierLabel(invitation.premium_tier)} pentru {invitation.premium_days || 30} zile</> : null}
        </div>
        <div className="auth-modal-action-row invite-provider-row">
          <a className="cal-btn auth-provider google" href={providerHref(AUTH_GOOGLE_PATH, returnTo)}>
            <FaGoogle aria-hidden="true" /> Google
          </a>
          <a className="cal-btn auth-provider facebook" href={providerHref(AUTH_FACEBOOK_PATH, returnTo)}>
            <FaFacebookF aria-hidden="true" /> Facebook
          </a>
        </div>
        <form className="form-stack invite-password-form" onSubmit={submitPassword} autoComplete="off">
          <label className="auth-field" htmlFor="invite-email">Email</label>
          <input
            id="invite-email"
            className="cal-input"
            name="username"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
            autoComplete="username"
          />
          <label className="auth-field" htmlFor="invite-password">Parola temporară din email</label>
          <input
            id="invite-password"
            className="cal-input"
            name="invite-temporary-password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            autoComplete="one-time-code"
            data-1p-ignore="true"
            data-lpignore="true"
          />
          <p className="auth-sub">Parola temporară poate fi schimbată ulterior din setările contului, dacă vrei.</p>
          <button className="cal-btn primary" type="submit" disabled={submitting}>{submitting ? "Se verifică..." : "Continuă cu parola"}</button>
          {status ? <div className="inline-error">{status}</div> : null}
        </form>
      </div>
    </PageShell>
  );
}

export default function AuthRoute({ route, user }) {
  if (route.name === "authLogin") return <AuthLoginRemovedView />;
  if (route.name === "authCallback") return <AuthCallbackView />;
  if (route.name === "invite") return <InvitationView route={route} user={user} />;
  return <AuthSetupView />;
}
