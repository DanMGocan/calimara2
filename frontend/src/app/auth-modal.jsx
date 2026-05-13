import { createContext, useContext, useEffect, useState } from "react";
import { SiFacebook, SiGoogle } from "react-icons/si";
import { AUTH_FACEBOOK_PATH, AUTH_GOOGLE_PATH, loginWithPassword } from "../api/auth.js";
import { mainPath } from "./paths.js";

const AuthModalContext = createContext({
  openAuthModal: null
});

export function AuthModalProvider({ value, children }) {
  return <AuthModalContext.Provider value={value}>{children}</AuthModalContext.Provider>;
}

export function useAuthModal() {
  return useContext(AuthModalContext);
}

function providerHref(path, returnTo) {
  if (!returnTo) return path;
  const query = new URLSearchParams({ return_to: returnTo });
  return `${path}?${query.toString()}`;
}

function navigateToAuthReturn(destination) {
  window.location.href = destination || mainPath("/");
}

export function AuthLoginModal({ open, returnTo, onClose, onAuthenticated }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  useEffect(() => {
    if (!open) return undefined;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  useEffect(() => {
    if (!open) {
      setEmail("");
      setPassword("");
      setStatus("");
      setSubmitting(false);
    }
  }, [open]);

  if (!open) return null;

  const submitLogin = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setStatus("");
    try {
      const response = await loginWithPassword({ email, password, return_to: returnTo || "" });
      await onAuthenticated?.();
      navigateToAuthReturn(response.redirect_url || returnTo || mainPath("/"));
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut autentifica acest cont.");
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-modal-scrim" role="presentation" onClick={onClose}>
      <section className="auth-modal" role="dialog" aria-modal="true" aria-labelledby="auth-modal-title" onClick={(event) => event.stopPropagation()}>
        <button className="auth-modal-close" type="button" aria-label="Închide" onClick={onClose}>x</button>
        <div className="piece-card-kicker">cont</div>
        <h2 id="auth-modal-title" className="auth-modal-title">Autentificare</h2>
        <form className="auth-modal-form" onSubmit={submitLogin}>
          <input
            id="auth-modal-email"
            className="cal-input"
            type="email"
            aria-label="Email"
            placeholder="Email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="email"
            required
            autoFocus
          />
          <input
            id="auth-modal-password"
            className="cal-input"
            type="password"
            aria-label="Parolă"
            placeholder="Parolă"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
            required
          />
          {status ? <div className="inline-error">{status}</div> : null}
          <div className="auth-modal-action-row">
            <button className="cal-btn primary auth-modal-submit" type="submit" disabled={submitting}>
              {submitting ? "Se autentifică..." : "Intră în cont"}
            </button>
            <a className="cal-btn auth-provider google" href={providerHref(AUTH_GOOGLE_PATH, returnTo)}>
              <SiGoogle aria-hidden="true" /> Google
            </a>
            <a className="cal-btn auth-provider facebook" href={providerHref(AUTH_FACEBOOK_PATH, returnTo)}>
              <SiFacebook aria-hidden="true" /> Facebook
            </a>
          </div>
        </form>
      </section>
    </div>
  );
}
